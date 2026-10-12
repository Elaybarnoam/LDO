"""Hash-verified descriptor analysis on frozen development pairs only."""

import argparse
import json
import shutil
from collections import Counter
from functools import lru_cache
from pathlib import Path

import numpy as np
import yaml

from ldo.artifacts import identity, sha256, write_json
from tasks.loop_closure.comparison.cli import publish_report

from .ranking import analyze

ROOT = Path(__file__).resolve().parents[4]
CONFIG = Path(__file__).with_name("config.yaml")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def total(rows: list[dict]) -> dict:
    counts = Counter()
    for row in rows:
        counts.update(row["metrics"])
    return dict(counts)


def run(settings: dict, output: Path) -> dict:
    source, diagnosis = Path(settings["source_root"]), Path(settings["diagnosis_root"])
    if settings["version"] != 1 or settings["minimum_correct_matches_per_pair"] != 20:
        raise ValueError("Preserve the version-1 20-match diagnostic")
    if settings["development_roles"] != ["fit", "validate"]:
        raise ValueError("Audit both original development splits; exclude test pairs")
    if settings["rank_budgets"] != [1, 5, 10, 50]:
        raise ValueError("Version 1 uses the predeclared rank budgets")
    if settings["cosine_tie_tolerance"] != 1e-7:
        raise ValueError("Version 1 uses the predeclared cosine tie tolerance")
    for path, expected in load(source / "experiment-freeze.json").items():
        if sha256(Path(path)) != expected:
            raise ValueError(f"Original frozen source changed: {path}")
    for path, expected in load(diagnosis / "analysis-freeze.json")["files"].items():
        if sha256(Path(path)) != expected:
            raise ValueError(f"Original diagnostic input changed: {path}")
    development = load(source / "development.json")
    summary_path = source / "variants" / development["baseline_id"] / "summary.json"
    baseline = load(summary_path)
    original = {(r["environment"], r["trajectory"], r["q"], r["h"]): r for r in baseline["rows"]}
    diagnostic = load(diagnosis / "results.json")
    feature_root = source / "features" / baseline["manifest"]["local_feature_fingerprint"]
    rows = diagnostic["development_pairs"]
    if len(rows) != 352 or Counter(r["split"] for r in rows) != {"fit": 224, "validate": 128}:
        raise ValueError("Expected the complete 352-pair positive development diagnosis")
    if len({(r["environment"], r["trajectory"], r["q"], r["h"]) for r in rows}) != len(rows):
        raise ValueError("Duplicate development pairs")
    if {r["environment"] for r in rows} != {"AbandonedFactory2", "DesertGasStation"}:
        raise ValueError("Only the original Factory and Desert development scenes are eligible")
    manifests = {
        (r["environment"], r["trajectory"]): feature_root
        / r["environment"]
        / r["trajectory"]
        / "manifest.json"
        for r in rows
    }
    input_paths = [
        source / "development.json",
        summary_path,
        source / "experiment-freeze.json",
        source / "fixed-pairs.json",
        diagnosis / "results.json",
        diagnosis / "analysis-freeze.json",
        *manifests.values(),
    ]
    code_paths = [
        CONFIG,
        *sorted(Path(__file__).parent.glob("*.py")),
        ROOT / "evaluation/src/tasks/matching_diagnostics/geometry.py",
        ROOT / "evaluation/src/modules/evaluation_file_handler/markdown_report.py",
    ]
    frozen = {
        "settings": settings,
        "inputs": {str(p): sha256(p) for p in input_paths},
        "code": {str(p): sha256(p) for p in code_paths},
    }
    output.mkdir(parents=True, exist_ok=True)
    marker = output / "analysis-freeze.json"
    if marker.exists() and load(marker) != frozen:
        raise ValueError("Analysis inputs changed; use a new artifact root")
    write_json(marker, frozen)
    for path in code_paths:
        target = output / "source" / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copyfile(path, target)
    feature_manifests = {key: load(path) for key, path in manifests.items()}

    @lru_cache(maxsize=128)
    def features(scene: str, trajectory: str, stamp: int, image: str):
        path = feature_root / scene / trajectory / f"{stamp}.npz"
        record = feature_manifests[scene, trajectory][str(stamp)]
        if sha256(path) != record["sha256"] or sha256(Path(image)) != record["image_sha256"]:
            raise ValueError(f"Original descriptor cache or input image changed: {path}")
        with np.load(path, allow_pickle=False) as cached:
            if str(cached["family"]) != "superpoint":
                raise ValueError(
                    "The descriptor audit is specific to the frozen SuperPoint baseline"
                )
            return cached["points"].copy(), cached["descriptors"].copy(), record["sha256"]

    measured = []
    for number, row in enumerate(rows, start=1):
        scene, trajectory, q, h = (row[k] for k in ("environment", "trajectory", "q", "h"))
        key = scene, trajectory, q, h
        if original[key]["label"] != "loop" or original[key]["split"] != row["split"]:
            raise ValueError("Development pair labels or splits changed")
        path = Path(row["evidence"])
        if sha256(path) != row["evidence_sha256"]:
            raise ValueError(f"Saved geometry edges changed: {path}")
        original_path = Path(row["source_evidence"])
        if sha256(original_path) != original[key]["sha256"]:
            raise ValueError("Original LightGlue assignment evidence changed")
        qp, qd, qhash = features(scene, trajectory, q, row["query_image"])
        hp, hd, hhash = features(scene, trajectory, h, row["historical_image"])
        with (
            np.load(path, allow_pickle=False) as saved,
            np.load(original_path, allow_pickle=False) as old,
        ):
            if not (
                np.array_equal(qp, saved["query_points"])
                and np.array_equal(hp, saved["historical_points"])
                and np.array_equal(saved["indices"], old["indices"])
                and np.array_equal(saved["verdicts"], old["verdicts"])
            ):
                raise ValueError(
                    "Descriptors, geometry and baseline feature indices are misaligned"
                )
            metrics, values = analyze(
                qd,
                hd,
                saved["supported_edges"],
                saved["indices"],
                saved["verdicts"],
                tuple(settings["rank_budgets"]),
                settings["cosine_tie_tolerance"],
                settings["minimum_correct_matches_per_pair"],
            )
        if metrics["maximum_supported_capacity"] != row["maximum_supported_one_to_one_matches"]:
            raise ValueError("Geometric capacity differs from the unchanged original diagnosis")
        destination = output / "pairs" / scene / trajectory / f"{q}_{h}.npz"
        destination.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(destination, **values)
        measured.append(
            {
                "environment": scene,
                "trajectory": trajectory,
                "q": q,
                "h": h,
                "split": row["split"],
                "metrics": metrics,
                "geometry_evidence_sha256": row["evidence_sha256"],
                "query_features_sha256": qhash,
                "historical_features_sha256": hhash,
                "baseline_evidence_sha256": original[key]["sha256"],
                "evidence": str(destination),
                "evidence_sha256": sha256(destination),
            }
        )
        if number % 32 == 0 or number == len(rows):
            print(f"Audited descriptor ranks: {number}/{len(rows)} development pairs", flush=True)
    result = {
        "schema_version": 1,
        "artifact_root": str(output),
        "freeze_sha256": identity(frozen),
        "baseline_id": development["baseline_id"],
        "baseline_manifest": baseline["manifest"],
        "rank_budgets": settings["rank_budgets"],
        "minimum_correct_matches_per_pair": 20,
        "development": {
            role: {
                "overall": total([r for r in measured if r["split"] == role]),
                "scenes": {
                    scene: total(
                        [r for r in measured if r["split"] == role and r["environment"] == scene]
                    )
                    for scene in sorted({r["environment"] for r in measured})
                },
            }
            for role in settings["development_roles"]
        },
        "pairs": measured,
        "model_changed": False,
        "reference_verdicts_changed": False,
        "fresh_test_performed": False,
        "training_performed": False,
    }
    write_json(output / "results.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    settings = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    output = args.output or Path(settings["artifact_root"])
    result = run(settings, output)
    report = publish_report(
        {"sequence": "LDO descriptor analysis", "descriptor_analysis": result},
        ROOT / "evaluation/output",
        CONFIG,
    )
    write_json(output / "report.json", {"report": str(report), "sha256": sha256(report)})
    print(report, flush=True)


if __name__ == "__main__":
    main()
