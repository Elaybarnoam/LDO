"""Develop pretrained matching variants, freeze selection, then evaluate fresh scenes."""

import argparse
import json
import shutil
from pathlib import Path

import yaml

from ldo.artifacts import sha256, write_json
from ldo.configuration import load_config
from loop_eval.tasks.loop_closure.comparison.cli import publish_report

from .engine import run_variant, threshold_variant
from .metrics import choose, eligible, measure
from .pairs import prepare
from .setup import CONFIG, ROOT, model_assets


def settings_and_freeze():
    settings = yaml.safe_load(CONFIG.read_text())
    if settings["version"] != 1:
        raise ValueError("Matching optimization requires version 1")
    root = Path(settings["artifact_root"])
    root.mkdir(parents=True, exist_ok=True)
    files = [
        CONFIG,
        ROOT / settings["baseline"],
        ROOT / settings["evaluator"],
        ROOT / "src/ldo/configuration.py",
        *sorted((ROOT / "ldo/matching").glob("*.py")),
        *sorted(Path(__file__).parent.glob("*.py")),
        ROOT / "src/loop_eval/tasks/reference_depth_v2/geometry.py",
        ROOT / "src/loop_eval/tasks/reference_geometry/geometry.py",
    ]
    freeze = {str(path): sha256(path) for path in files}
    marker = root / "experiment-freeze.json"
    if marker.exists() and json.loads(marker.read_text()) != freeze:
        raise ValueError("Experiment source/config changed; use a new artifact root")
    write_json(marker, freeze)
    source = root / "source"
    source.mkdir(exist_ok=True)
    for path in files:
        relative = path.relative_to(ROOT)
        target = source / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copyfile(path, target)
    return settings, root


def enrich(result, policy):
    result = {**result}
    for split in ("fit", "validate"):
        result[split] = measure(
            [r for r in result["rows"] if r["split"] == split],
            policy["minimum_correct_matches_per_pair"],
        )
    return result


def develop():
    settings, root = settings_and_freeze()
    model_assets(settings)
    base_file = yaml.safe_load((ROOT / settings["baseline"]).read_text())
    base_file["model_root"] = settings["model_root"]
    base_path = root / "baseline.yaml"
    write = yaml.safe_dump(base_file, sort_keys=False)
    base_path.write_text(write)
    base = load_config(base_path)
    policy = yaml.safe_load((ROOT / settings["evaluator"]).read_text())
    assets = json.loads(Path(policy["asset_root"]).joinpath("installation.json").read_text())
    contexts = prepare(settings, ROOT, root)
    baseline_variant = {
        "family": "superpoint",
        "keypoints": 1024,
        "resize": None,
        "full_depth": False,
        "threshold": 0.3,
    }
    all_results = {}

    def evaluate(variant):
        result = enrich(run_variant(contexts, base, variant, assets, policy, root), settings)
        all_results[result["id"]] = result
        return result

    baseline = evaluate(baseline_variant)
    orb = enrich(
        run_variant(contexts, base, {"family": "orb"}, assets, policy, root, orb=True), settings
    )
    current = baseline
    decisions = []

    def decide(name, candidates):
        nonlocal current
        selected = choose(candidates, baseline["fit"], current, settings)
        proposed_change = selected["id"] != current["id"]
        validation_passed = (
            eligible(baseline["validate"], selected["validate"], settings)
            and selected["validate"]["overall"]["contradicted"]
            < current["validate"]["overall"]["contradicted"]
        )
        promoted = proposed_change and validation_passed
        previous = current["id"]
        if promoted:
            current = selected
        decision = {
            "step": name,
            "previous": previous,
            "fit_selected": selected["id"],
            "promoted": promoted,
            "validation_passed": validation_passed,
            "selected_after_step": current["id"],
            "candidate_ids": [r["id"] for r in candidates],
        }
        decisions.append(decision)
        write_json(root / "progress.json", {"steps": decisions, "selected": current["variant"]})
        print(
            f"STEP {name}: promoted={promoted}; selected=" + json.dumps(current["variant"]),
            flush=True,
        )

    threshold_results = []
    for threshold in settings["thresholds"]:
        result = (
            baseline
            if threshold == 0.3
            else enrich(threshold_variant(baseline, threshold, root), settings)
        )
        all_results[result["id"]] = result
        threshold_results.append(result)
    decide("confidence", threshold_results)
    decide("full_depth", [evaluate({**current["variant"], "full_depth": True})])
    decide(
        "keypoint_count",
        [
            evaluate({**current["variant"], "keypoints": count})
            for count in settings["keypoint_counts"]
        ],
    )
    decide(
        "image_resolution",
        [evaluate({**current["variant"], "resize": resize}) for resize in settings["resolutions"]],
    )
    decide("feature_family", [evaluate({**current["variant"], "family": "aliked"})])
    selected_config = {
        **base_file,
        "variant": "LDO-MegaLoc-"
        + current["variant"]["family"].title()
        + "-LightGlue-MatchingOptimized",
        "matching": f"{current['variant']['family']}_lightglue",
        "maximum_keypoints": current["variant"]["keypoints"],
        "feature_resize": current["variant"]["resize"],
        "matcher_full_depth": current["variant"]["full_depth"],
        "match_threshold": current["variant"]["threshold"],
    }
    selected_path = ROOT / "configs/models/optimized-matching.yaml"
    selected_path.write_text(yaml.safe_dump(selected_config, sort_keys=False))
    result = {
        "baseline_id": baseline["id"],
        "selected_id": current["id"],
        "baseline": baseline["variant"],
        "selected": current["variant"],
        "steps": decisions,
        "orb": {s: orb[s] for s in ("fit", "validate")},
        "variants": [
            {k: r[k] for k in ("id", "variant", "fit", "validate")} for r in all_results.values()
        ],
        "fixed_pairs_sha256": sha256(root / "fixed-pairs.json"),
        "experiment_freeze_sha256": sha256(root / "experiment-freeze.json"),
        "selected_configuration": str(selected_path),
        "selected_configuration_sha256": sha256(selected_path),
        "selected_before_test": True,
        "training_performed": False,
    }
    marker = root / "development.json"
    if marker.exists() and json.loads(marker.read_text()) != result:
        raise ValueError("Development choices changed after freezing")
    write_json(marker, result)
    print("Frozen matching selection: " + json.dumps(result["selected"]), flush=True)
    return result


def publish(settings, root):
    result = {
        "development": json.loads((root / "development.json").read_text()),
        "test": json.loads((root / "test-results.json").read_text())
        if (root / "test-results.json").exists()
        else None,
        "configuration": settings,
        "artifact_root": str(root),
    }
    path = publish_report(
        {"sequence": "LDO matching optimization", "matching_optimization": result},
        ROOT / "evaluation/output",
        CONFIG,
    )
    write_json(
        ROOT / "evaluation/output/matching-optimization.json",
        {"report": str(path), "sha256": sha256(path)},
    )
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("develop", "test", "all", "report"))
    args = parser.parse_args()
    if args.command in ("develop", "all"):
        develop()
    settings, root = settings_and_freeze()
    if args.command in ("test", "all"):
        from .heldout import run

        run(settings, root)
    print(publish(settings, root), flush=True)


if __name__ == "__main__":
    main()
