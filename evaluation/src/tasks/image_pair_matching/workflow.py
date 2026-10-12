"""One frozen image-pair matcher, identical pairs and unchanged external checks."""

import argparse
import json
import shutil
from functools import partial
from pathlib import Path
from time import perf_counter

import numpy as np
import yaml

from ldo.artifacts import identity, sha256, write_json
from ldo.matching.efficientloftr import EfficientLoFTRMatcher
from tasks.loop_closure.comparison.cli import publish_report
from tasks.matching_optimization.engine import references
from tasks.matching_optimization.metrics import measure
from tasks.reference_depth_v2.geometry import check_features

from .metrics import assess
from .setup import prepare

ROOT = Path(__file__).resolve().parents[4]
CONFIG = Path(__file__).with_name("config.yaml")


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def run(settings):
    import torch

    source, output = Path(settings["source_root"]), Path(settings["artifact_root"])
    output.mkdir(parents=True, exist_ok=True)
    if settings["version"] != 1 or (settings["threshold"], settings["maximum_matches"]) != (
        0.2,
        1024,
    ):
        raise ValueError("Use the single predeclared candidate configuration")
    for path, expected in load(source / "experiment-freeze.json").items():
        if sha256(Path(path)) != expected:
            raise ValueError(f"Original frozen source changed: {path}")
    development = load(source / "development.json")
    baseline_path = source / "variants" / development["baseline_id"] / "summary.json"
    baseline = load(baseline_path)
    fixed = load(source / "fixed-pairs.json")
    if identity(fixed["contexts"]) != baseline["contexts_sha256"]:
        raise ValueError("Original pair contexts changed")
    if sum(len(c["pairs"]) for c in fixed["contexts"]) != 880:
        raise ValueError("Use all 880 frozen development pairs")
    policy_path = ROOT / settings["evaluator"]
    policy = yaml.safe_load(policy_path.read_text())
    assets_path = Path(policy["asset_root"]) / "installation.json"
    assets = load(assets_path)
    installation = prepare(Path(settings["model_root"]))
    files = [
        CONFIG,
        policy_path,
        baseline_path,
        source / "development.json",
        source / "fixed-pairs.json",
        source / "experiment-freeze.json",
        assets_path,
        Path(settings["model_root"]) / "manifest.json",
        *sorted(Path(__file__).parent.glob("*.py")),
        ROOT / "ldo/matching/efficientloftr.py",
        ROOT / "ldo/matching/image_pairs.py",
    ]
    frozen = {"settings": settings, "files": {str(p): sha256(p) for p in files}}
    marker = output / "experiment-freeze.json"
    if marker.exists() and load(marker) != frozen:
        raise ValueError("Trial source/configuration changed; use a new artifact root")
    write_json(marker, frozen)
    for path in files:
        if path.is_relative_to(ROOT):
            destination = output / "source" / path.relative_to(ROOT)
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not destination.exists():
                shutil.copyfile(path, destination)
    torch.manual_seed(settings["seed"])
    np.random.seed(settings["seed"])
    torch.set_num_threads(1)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    original = {(r["environment"], r["trajectory"], r["q"], r["h"]): r for r in baseline["rows"]}
    matcher = EfficientLoFTRMatcher(
        Path(settings["model_root"]),
        settings["device"],
        settings["threshold"],
        settings["maximum_matches"],
    )
    measured, semantic_hashes, parity_count = [], {}, 0
    try:
        for context in fixed["contexts"]:
            if context["split"] not in ("fit", "validate") or context["environment"] not in (
                "AbandonedFactory2",
                "DesertGasStation",
            ):
                raise ValueError("Only the original Factory/Desert development data are eligible")
            items, depths, masks, poses, labels, hashes = references(context, assets)
            if any(baseline["semantic_sha256"].get(path) != h for path, h in hashes.items()):
                raise ValueError("Original reference semantics changed")
            semantic_hashes.update(hashes)
            destination = output / "pairs" / context["environment"] / context["trajectory"]
            destination.mkdir(parents=True, exist_ok=True)
            for pair in context["pairs"]:
                q, h = pair["q"], pair["h"]
                old = original[context["environment"], context["trajectory"], q, h]
                if old["label"] != pair["label"] or old["split"] != context["split"]:
                    raise ValueError("Pair labels or splits changed")
                if sha256(Path(old["evidence"])) != old["sha256"]:
                    raise ValueError("Original baseline evidence changed")
                relative = np.linalg.inv(poses[h]) @ poses[q]

                evaluate = partial(
                    check_features,
                    query_depth=depths[q],
                    historical_depth=depths[h],
                    query_sem=masks[q],
                    historical_sem=masks[h],
                    relative=relative,
                    known_labels=set(labels.values()),
                    sky_label=labels["sky"],
                    policy=policy,
                )

                with np.load(old["evidence"], allow_pickle=False) as saved:
                    parity = evaluate(saved["query_points"], saved["historical_points"])
                    if not np.array_equal(parity["verdicts"], saved["verdicts"]):
                        raise ValueError(
                            "Candidate environment changes original reference verdicts"
                        )
                parity_count += 1
                torch.cuda.synchronize()
                started = perf_counter()
                matches = matcher.match_images(Path(items[q]["image"]), Path(items[h]["image"]))
                torch.cuda.synchronize()
                elapsed = (perf_counter() - started) * 1000
                checked = evaluate(matches.query_points, matches.historical_points)
                path = destination / f"{q}_{h}.npz"
                np.savez_compressed(
                    path,
                    query_points=matches.query_points,
                    historical_points=matches.historical_points,
                    scores=matches.scores,
                    **checked,
                )
                counts = {
                    k: int(np.sum(checked["verdicts"] == k))
                    for k in ("supported", "contradicted", "untestable")
                }
                measured.append(
                    {
                        **pair,
                        "environment": context["environment"],
                        "trajectory": context["trajectory"],
                        "split": context["split"],
                        "counts": counts,
                        "matching_ms": elapsed,
                        "evidence": str(path),
                        "sha256": sha256(path),
                    }
                )
            print(
                f"Completed {context['environment']}/{context['trajectory']}: {len(measured)}/880 pairs",
                flush=True,
            )
    finally:
        matcher.close()
    candidate = {
        "id": "efficientloftr-native-full-0.2-1024",
        "variant": {
            "engine": "efficientloftr",
            "precision": "fp32",
            "resize": None,
            "threshold": settings["threshold"],
            "maximum_matches": settings["maximum_matches"],
        },
        **{
            role: measure([r for r in measured if r["split"] == role], 20)
            for role in ("fit", "validate")
        },
    }
    base = {
        "id": development["baseline_id"],
        "variant": development["baseline"],
        **{
            role: measure([r for r in baseline["rows"] if r["split"] == role], 20)
            for role in ("fit", "validate")
        },
    }
    gates = {role: assess(base[role], candidate[role], settings) for role in ("fit", "validate")}
    passed = all(g["passed"] for g in gates.values())
    result = {
        "schema_version": 1,
        "artifact_root": str(output),
        "freeze_sha256": identity(frozen),
        "installation": installation,
        "matcher_fingerprint": matcher.fingerprint,
        "baseline": base,
        "candidate": candidate,
        "gates": gates,
        "preliminary_pair_gates_passed": passed,
        "ready_for_event_replay": passed,
        "baseline_verdict_parity_pairs": parity_count,
        "rows": measured,
        "semantic_sha256": semantic_hashes,
        "production_model_changed": False,
        "event_replay_performed": False,
        "fresh_test_performed": False,
    }
    write_json(output / "results.json", result)
    # Reuse the existing shared-pair matching report schema and sole FIFO writer.
    report_data = {
        "artifact_root": str(output),
        "test": None,
        "development": {
            "steps": [
                {
                    "step": "EfficientLoFTR preliminary pair gate; production promotion pending",
                    "fit_selected": candidate["id"] if gates["fit"]["passed"] else base["id"],
                    "promoted": False,
                    "selected_after_step": base["id"],
                }
            ],
            "variants": [base, candidate],
            "orb": development["orb"],
            "selected": development["baseline"],
            "fixed_pairs_sha256": sha256(source / "fixed-pairs.json"),
            "experiment_freeze_sha256": identity(frozen),
            "selected_configuration_sha256": sha256(ROOT / "ldo/configs/optimized-confidence.yaml"),
        },
    }
    report = publish_report(
        {"sequence": settings["variant"], "matching_optimization": report_data},
        ROOT / "evaluation/output",
        CONFIG,
    )
    write_json(output / "report.json", {"report": str(report), "sha256": sha256(report)})
    print(json.dumps({"gates": gates, "report": str(report)}), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    settings = yaml.safe_load(CONFIG.read_text())
    if args.output:
        settings["artifact_root"] = str(args.output)
    run(settings)


if __name__ == "__main__":
    main()
