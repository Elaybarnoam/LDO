"""Development-selected confidence sweep and candidate policy, stages one and two."""

import json

import numpy as np
import yaml
from scipy.optimize import minimize
from scipy.special import expit

from ldo.policies.confidence import FEATURE_NAMES, CandidateConfidencePolicy
from loop_eval.paths import project_root

from .observations import change, load, measure

ROOT = project_root()
FIT = [f"P{i:03d}" for i in range(5)]
VALIDATE = ["P005", "P006"]
DEFAULT_REPORT = ROOT / "evaluation/output/comparison_2026-10-09_18-09-31_019938_54b2f5f8.json"
OUT = ROOT / "evaluation/output/optimization/development"


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2))


def step1():
    pairs, contexts = load(DEFAULT_REPORT)
    base = measure(pairs, contexts, trajectories=FIT)
    sweep = []
    for threshold in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9):
        result = measure(pairs, contexts, threshold, trajectories=FIT)
        sweep.append({"threshold": threshold, "metrics": result, "change": change(base, result)})
    feasible = [r for r in sweep if r["change"]["supported_match_retention"] >= 0.9]
    selected = min(
        feasible,
        key=lambda r: (
            r["metrics"]["features"]["contradicted"],
            -r["metrics"]["features"]["supported"],
        ),
    )
    threshold = selected["threshold"]
    validation_base = measure(pairs, contexts, trajectories=VALIDATE)
    validation = measure(pairs, contexts, threshold, trajectories=VALIDATE)
    result = {
        "step": 1,
        "selection_data": FIT,
        "validation_data": VALIDATE,
        "threshold": threshold,
        "sweep": sweep,
        "validation_baseline": validation_base,
        "validation": validation,
        "validation_change": change(validation_base, validation),
        "all_development": measure(pairs, contexts, threshold),
    }
    save(OUT / "step1.json", result)
    config = yaml.safe_load((ROOT / "configs/evaluation/reference_geometry/ldo.yaml").read_text())
    config.update(variant="LDO-MegaLoc-LightGlue-Confidence", match_threshold=threshold)
    (ROOT / "configs/models/optimized-confidence.yaml").write_text(
        yaml.safe_dump(config, sort_keys=False)
    )
    print("STEP1", json.dumps(result["validation_change"]), "threshold", threshold, flush=True)
    return result


def step2():
    first = json.loads((OUT / "step1.json").read_text())
    threshold = first["threshold"]
    pairs, contexts = load(DEFAULT_REPORT)
    fit = [r for r in pairs if r.trajectory in FIT and r.label in ("loop", "non_loop")]
    x = np.stack([r.vector(threshold) for r in fit])
    y = np.array([r.label == "loop" for r in fit], float)
    mean, scale = x.mean(axis=0), np.maximum(x.std(axis=0), 1e-6)
    z = (x - mean) / scale

    def loss(w):
        logits = z @ w[:-1] + w[-1]
        value = np.mean(np.logaddexp(0, logits) - y * logits) + 0.01 * np.dot(w[:-1], w[:-1]) / 2
        residual = expit(logits) - y
        gradient = np.r_[z.T @ residual / len(y) + 0.01 * w[:-1], residual.mean()]
        return value, gradient

    fitted = minimize(loss, np.zeros(x.shape[1] + 1), jac=True, method="L-BFGS-B")
    if not fitted.success or not np.isfinite(fitted.x).all():
        raise RuntimeError(f"Policy fitting failed: {fitted.message}")
    params = {
        "feature_names": list(FEATURE_NAMES),
        "mean": mean.tolist(),
        "scale": scale.tolist(),
        "weights": fitted.x[:-1].tolist(),
        "bias": float(fitted.x[-1]),
        "threshold": 0.0,
        "fit_trajectories": FIT,
        "match_threshold": threshold,
        "calibration_status": "development_fitted_score_not_guaranteed_test_probability",
    }
    policy = CandidateConfidencePolicy(params)
    validation = [r for r in pairs if r.trajectory in VALIDATE]
    base = measure(pairs, contexts, threshold, trajectories=VALIDATE)
    cuts = sorted({0.0, *[policy.score(r.vector(threshold)) for r in validation]})
    sweep = []
    for cut in cuts:
        policy.threshold = cut
        m = measure(pairs, contexts, threshold, policy, VALIDATE)
        delta = change(base, m)
        if delta["true_candidate_retention"] >= 0.9 and delta["confirmed_event_retention"] >= 0.9:
            sweep.append(
                (
                    m["candidates"]["false_positive_pairs"],
                    -m["candidates"]["true_positive_pairs"],
                    cut,
                    m,
                    delta,
                )
            )
    _, _, cut, validation_metrics, delta = min(sweep, key=lambda r: r[:3])
    params["threshold"] = cut
    policy = CandidateConfidencePolicy(params)
    save(ROOT / "configs/models/candidate-confidence.json", params)
    result = {
        "step": 2,
        "fit_data": FIT,
        "selection_data": VALIDATE,
        "parameters": params,
        "validation_baseline": base,
        "validation": validation_metrics,
        "validation_change": delta,
        "all_development": measure(pairs, contexts, threshold, policy),
    }
    save(OUT / "step2.json", result)
    config = yaml.safe_load((ROOT / "configs/models/optimized-confidence.yaml").read_text())
    config.update(
        variant="LDO-MegaLoc-LightGlue-ConfidencePolicy",
        policy="candidate_confidence",
        policy_parameters="candidate-confidence.json",
    )
    (ROOT / "configs/models/optimized-policy.yaml").write_text(
        yaml.safe_dump(config, sort_keys=False)
    )
    print("STEP2", json.dumps(delta), "cutoff", cut, flush=True)
    return result


if __name__ == "__main__":
    step1()
    step2()
