"""One frozen held-out environment experiment; never selects parameters on test data."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import torch
import yaml

from ldo.artifacts import sha256
from ldo.configuration import load_config
from ldo.matching.lightglue import LightGlueMatcher
from ldo.policies.confidence import CandidateConfidencePolicy
from loop_eval.paths import configuration_path
from loop_eval.tasks.reference_geometry.cli import validate_config
from loop_eval.tasks.reference_geometry.direct import run
from loop_eval.tasks.reference_geometry.workflow import prepare

from .develop import OUT, ROOT, save
from .observations import change, load, measure, read_summary
from .training import FeatureCache, rescore

CONFIG = configuration_path("configs/evaluation/optimization/test.yaml")
HELDOUT = ROOT / "evaluation/output/optimization/heldout"


def prepare_test():
    config = yaml.safe_load(
        (ROOT / "configs/evaluation/reference_geometry/config.yaml").read_text()
    )
    config["dataset"].update(
        root="/opt/loop-detector/datasets/tartanair_optimization/test",
        environment="CountryHouse",
        trajectories=[f"P{i:03d}" for i in range(6)],
        reference_only=False,
    )
    # The native ORB evidence exporter requires real synchronized cam1 images;
    # neither detector nor the independent scorer uses them for decisions here.
    CONFIG.write_text(yaml.safe_dump(config, sort_keys=False))
    validate_config(config)
    prepared = prepare(config, CONFIG)
    save(HELDOUT / "prepared.json", {"path": str(prepared), "config_sha256": sha256(CONFIG)})
    return prepared


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "run"))
    args = parser.parse_args()
    if args.command == "prepare":
        print(prepare_test(), flush=True)
        return
    # Refuse to evaluate test models until all development choices are frozen.
    step1 = json.loads((OUT / "step1.json").read_text())
    step2 = json.loads((OUT / "step2.json").read_text())
    step3 = json.loads((OUT / "step3.json").read_text())
    policy = CandidateConfidencePolicy.from_file(
        ROOT / "configs/models/candidate-confidence.json"
    )
    selected = step3["selected"]
    frozen = {
        "steps": [step1, step2, step3],
        "frozen_before_test_inference": True,
        "configuration_sha256": {
            p.name: sha256(p) for p in (ROOT / "configs/models").glob("optimized*.yaml")
        },
        "policy_sha256": sha256(ROOT / "configs/models/candidate-confidence.json"),
    }
    freeze_path = HELDOUT / "frozen_variants.json"
    if freeze_path.exists():
        if json.loads(freeze_path.read_text()) != frozen:
            raise ValueError("Development choices changed after test freeze")
    else:
        save(freeze_path, frozen)
    config = yaml.safe_load(CONFIG.read_text())
    prepared = json.loads((HELDOUT / "prepared.json").read_text())
    if sha256(CONFIG) != prepared["config_sha256"]:
        raise ValueError("Held-out configuration changed")
    marker = HELDOUT / "baseline.json"
    if marker.exists():
        baseline_path = Path(json.loads(marker.read_text())["path"])
    else:
        baseline_path = run(config, CONFIG, Path(prepared["path"]))
        save(marker, {"path": str(baseline_path), "sha256": sha256(baseline_path)})
    marker_data = json.loads(marker.read_text())
    if sha256(baseline_path) != marker_data["sha256"]:
        raise ValueError("Held-out baseline report changed")
    pairs, contexts = load(baseline_path)
    threshold = step1["threshold"]
    baseline = measure(pairs, contexts)
    confidence = measure(pairs, contexts, threshold)
    filtered = measure(pairs, contexts, threshold, policy)
    print("TEST STEP1", json.dumps(change(baseline, confidence)), flush=True)
    print("TEST STEP2", json.dumps(change(confidence, filtered)), flush=True)
    model_config = load_config(ROOT / "configs/evaluation/reference_geometry/ldo.yaml")
    torch.set_num_threads(1)
    cache = FeatureCache(model_config)
    control = LightGlueMatcher(
        torch.device(model_config.device), "superpoint", 0.1, full_depth=True
    )
    control_pairs = rescore(
        control, cache, pairs, contexts, config["protocol"], HELDOUT / "full_depth_control"
    )
    control_metrics = measure(control_pairs, contexts, threshold, policy)
    control.close()
    adapted = None
    if selected:
        matcher = LightGlueMatcher(
            torch.device(model_config.device),
            "superpoint",
            0.1,
            checkpoint=Path(selected["checkpoint"]),
            checkpoint_sha256=selected["checkpoint_sha256"],
            full_depth=True,
        )
        adapted_pairs = rescore(
            matcher, cache, pairs, contexts, config["protocol"], HELDOUT / "adapted_head"
        )
        adapted = measure(adapted_pairs, contexts, threshold, policy)
        matcher.close()
    cache.close()
    deployed = adapted if step3["promoted"] else filtered
    task = read_summary(baseline_path)["reference_geometry"]
    result = {
        "experiment": "sequential_ldo_optimization",
        "created_at": datetime.now(UTC).isoformat(),
        "test_environment": "CountryHouse",
        "test_trajectories": list(contexts),
        "freeze_manifest_sha256": sha256(freeze_path),
        "baseline_report": str(baseline_path),
        "reference_geometry_code_sha256": task["manifest"]["reference_geometry_code_sha256"],
        "test_was_used_for_parameter_selection": False,
        "variants": {
            "baseline": baseline,
            "confidence": confidence,
            "candidate_policy": filtered,
            "full_depth_control": control_metrics,
            "adapted_head": adapted,
            "development_selected": deployed,
        },
        "steps": {
            "1": change(baseline, confidence),
            "2": change(confidence, filtered),
            "3": change(filtered, adapted) if adapted else None,
            "learning_vs_equal_compute": change(control_metrics, adapted) if adapted else None,
            "overall": change(baseline, deployed),
        },
        "orb": task["aggregate"],
        "development": {
            "1": step1["validation_change"],
            "2": step2["validation_change"],
            "3": selected["change_from_step2"] if selected else None,
            "training_promoted": step3["promoted"],
        },
        "limitations": [
            "One held-out synthetic environment; upstream pretraining overlap unaudited.",
            "Unknown reference matches remain unknown, not incorrect.",
            "Candidate labels use frozen 20% bidirectional visible overlap; not pose accuracy.",
            "No latency or real-world SLAM improvement claim from this experiment.",
        ],
    }
    save(HELDOUT / "results.json", result)
    from .report import publish

    print(publish(result, CONFIG), flush=True)


if __name__ == "__main__":
    main()
