"""Audit frozen test failures and verify their pattern on separate development data."""

import argparse
import json
import shutil
from collections import Counter
from pathlib import Path

import numpy as np
import yaml

from ldo.artifacts import identity, sha256, write_json
from tasks.loop_closure.comparison.cli import publish_report
from tasks.matching_optimization.engine import references
from tasks.reference_geometry.detectors import FeaturePairs

from .geometry import analyze

ROOT = Path(__file__).resolve().parents[4]
CONFIG = Path(__file__).with_name("config.yaml")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def freeze(settings: dict, source: Path, output: Path) -> dict:
    old = load_json(source / "experiment-freeze.json")
    for name, expected in old.items():
        if sha256(Path(name)) != expected:
            raise ValueError(f"Frozen original source/configuration changed: {name}")
    files = [CONFIG, *sorted(Path(__file__).parent.glob("*.py")), *map(Path, old)]
    files += [
        source / name
        for name in (
            "test-results.json",
            "test-freeze.json",
            "development.json",
            "fixed-pairs.json",
            "semantic-assets.json",
            "heldout-runtime-audit.json",
        )
    ]
    frozen = {"settings": settings, "files": {str(p): sha256(p) for p in files}}
    marker = output / "analysis-freeze.json"
    if marker.exists() and load_json(marker) != frozen:
        raise ValueError("Analysis inputs changed; use a new artifact root")
    write_json(marker, frozen)
    snapshots = output / "source"
    snapshots.mkdir(exist_ok=True)
    for file in files:
        if file.is_relative_to(ROOT):
            destination = snapshots / file.relative_to(ROOT)
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not destination.exists():
                shutil.copyfile(file, destination)
    return frozen


def missed_events(source: Path, test: dict, minimum: int) -> list[dict]:
    cases = []
    count = 0
    for info, seq in zip(test["manifest"]["sequences"], test["sequences"], strict=True):
        trace_path = Path(seq["methods"]["baseline"]["trace"])
        if sha256(trace_path) != seq["methods"]["baseline"]["trace_sha256"]:
            raise ValueError("Original baseline retrieval changed")
        trace = {
            row["query_timestamp_ns"]: row["candidates"]
            for row in map(json.loads, trace_path.read_text().splitlines())
        }
        event_path = Path(info["root"]) / "events.json"
        if sha256(event_path) != info["events_sha256"]:
            raise ValueError("Original event definitions changed")
        for event in load_json(event_path):
            pairs = []
            for q in event["query_timestamps"]:
                positive = set(event["historical_by_query"][str(q)])
                for c in trace[q]:
                    h = c["historical_timestamp_ns"]
                    if h in positive:
                        path = (
                            source / "heldout-checks/baseline" / seq["trajectory"] / f"{q}_{h}.npz"
                        )
                        with np.load(path, allow_pickle=False) as saved:
                            good = int(np.sum(saved["verdicts"] == "supported"))
                        pairs.append({"q": q, "h": h, "label": "loop", "saved_correct": good})
            best = max((p["saved_correct"] for p in pairs), default=0)
            count += best >= minimum
            if best < minimum:
                cases.append(
                    {
                        "environment": test["manifest"]["dataset"]["environment"],
                        "trajectory": seq["trajectory"],
                        "reference": info,
                        "event": event,
                        "trace": str(trace_path),
                        "pairs": pairs,
                        "semantic_sha256": seq["methods"]["baseline"]["semantic_sha256"],
                    }
                )
    if count != test["aggregate"]["baseline"]["usable_event_hits"]:
        raise ValueError("Saved feature evidence disagrees with original event counts")
    return cases


def analyze_context(
    context: dict,
    assets: dict,
    policy: dict,
    output: Path,
    source: Path,
    baseline: dict | None = None,
) -> list[dict]:
    items, depths, masks, poses, labels, semantic_hashes = references(context, assets)
    for path, expected in semantic_hashes.items():
        if context["semantic_sha256"].get(path) != expected:
            raise ValueError("Semantic evidence differs from the original scoring run")
    features = None
    if baseline is None:
        evidence_root = Path(context["trace"]).parent
        features = FeaturePairs(
            evidence_root, "ldo", {s: Path(f["image"]) for s, f in items.items()}
        )
    else:
        feature_root = (
            source
            / "features"
            / baseline["manifest"]["local_feature_fingerprint"]
            / context["environment"]
            / context["trajectory"]
        )
        feature_manifest = load_json(feature_root / "manifest.json")
        cache = {}

        def cached_points(stamp):
            if stamp not in cache:
                path = feature_root / f"{stamp}.npz"
                record = feature_manifest[str(stamp)]
                if (
                    sha256(path) != record["sha256"]
                    or items[stamp]["image_sha256"] != record["image_sha256"]
                ):
                    raise ValueError("Original development features changed")
                with np.load(path, allow_pickle=False) as saved:
                    cache[stamp] = saved["points"].copy()
            return cache[stamp]

    rows = []
    for pair in context["pairs"]:
        q, h = pair["q"], pair["h"]
        if features is not None:
            qp, _ = features.features(q)
            hp, _ = features.features(h)
            indices = features.assignments(q, h)
            original_path = (
                source / "heldout-checks/baseline" / context["trajectory"] / f"{q}_{h}.npz"
            )
        else:
            qp, hp = cached_points(q), cached_points(h)
            original_path = Path(pair["evidence"])
            if sha256(original_path) != pair["sha256"]:
                raise ValueError("Original development assignments changed")
            with np.load(original_path, allow_pickle=False) as saved:
                indices = saved["indices"].copy()
        summary, values = analyze(
            qp,
            hp,
            indices,
            depths[q],
            depths[h],
            masks[q],
            masks[h],
            np.linalg.inv(poses[h]) @ poses[q],
            set(labels.values()),
            labels["sky"],
            policy,
        )
        with np.load(original_path, allow_pickle=False) as saved:
            if not np.array_equal(values["verdicts"], saved["verdicts"]):
                raise ValueError("Recomputed verdicts differ from the frozen evaluator")
        destination = output / context["environment"] / context["trajectory"] / f"{q}_{h}.npz"
        destination.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(destination, **values)
        rows.append(
            {
                "q": q,
                "h": h,
                "environment": context["environment"],
                "trajectory": context["trajectory"],
                "split": context.get("split", "post_test_diagnosis"),
                "query_image": items[q]["image"],
                "historical_image": items[h]["image"],
                "source_evidence": str(original_path),
                "source_evidence_sha256": sha256(original_path),
                "evidence": str(destination),
                "evidence_sha256": sha256(destination),
                **summary,
            }
        )
    return rows


def summarize(rows: list[dict], minimum: int) -> dict:
    totals = Counter()
    for row in rows:
        totals.update(row["reported"])
    return {
        "pairs": len(rows),
        "reported": dict(totals),
        "usable_pairs": sum(r["reported"]["supported"] >= minimum for r in rows),
        "oracle_usable_pairs": sum(
            r["maximum_supported_one_to_one_matches"] >= minimum for r in rows
        ),
        "assignment_gap_pairs": sum(
            r["reported"]["supported"] < minimum <= r["maximum_supported_one_to_one_matches"]
            for r in rows
        ),
        "capacity_limited_pairs": sum(
            r["maximum_supported_one_to_one_matches"] < minimum for r in rows
        ),
        "near_gate_contradictions": sum(r["contradictions_near_geometric_gates"] for r in rows),
        "large_residual_contradictions": sum(
            r["contradictions_with_large_geometric_residuals"] for r in rows
        ),
    }


def run(settings: dict, output: Path) -> dict:
    source = Path(settings["source_root"])
    frozen = freeze(settings, source, output)
    test = load_json(source / "test-results.json")
    audit = load_json(source / "heldout-runtime-audit.json")
    if audit["test_results_sha256"] != sha256(source / "test-results.json"):
        raise ValueError("Original test results differ from their audit")
    policy = yaml.safe_load((ROOT / settings["evaluator"]).read_text())
    minimum = settings["minimum_correct_matches_per_pair"]
    if minimum != 20 or settings["version"] != 1:
        raise ValueError("This diagnosis preserves the original version-1 20-match diagnostic")
    assets = load_json(source / "semantic-assets.json")
    cases = missed_events(source, test, minimum)
    event_results, test_rows = [], []
    for case in cases:
        rows = analyze_context(case, assets, policy, output / "pairs/test", source)
        test_rows.extend(rows)
        capacity = max((r["maximum_supported_one_to_one_matches"] for r in rows), default=0)
        event_results.append(
            {
                "environment": case["environment"],
                "trajectory": case["trajectory"],
                "event_id": case["event"]["event_id"],
                "start_ns": case["event"]["start_ns"],
                "end_ns": case["event"]["end_ns"],
                "best_reported_correct": max((r["reported"]["supported"] for r in rows), default=0),
                "maximum_existing_feature_capacity": capacity,
                "diagnosis": "assignment_gap_possible"
                if capacity >= minimum
                else "existing_feature_capacity_below_diagnostic",
                "pairs": rows,
            }
        )
        print(
            f"Diagnosed {case['trajectory']}/{case['event']['event_id']}: capacity={capacity}",
            flush=True,
        )
    development = load_json(source / "development.json")
    baseline = load_json(source / "variants" / development["baseline_id"] / "summary.json")
    fixed = load_json(source / "fixed-pairs.json")
    if baseline["contexts_sha256"] != identity(fixed["contexts"]):
        raise ValueError("Original development pair contexts changed")
    original = {(r["environment"], r["trajectory"], r["q"], r["h"]): r for r in baseline["rows"]}
    dev_assets = load_json(Path(policy["asset_root"]) / "installation.json")
    dev_rows = []
    for context in fixed["contexts"]:
        if context["split"] not in settings["development_roles"]:
            continue
        pairs = [
            original[context["environment"], context["trajectory"], p["q"], p["h"]]
            for p in context["pairs"]
            if p["label"] == "loop"
        ]
        context = {**context, "pairs": pairs, "semantic_sha256": baseline["semantic_sha256"]}
        rows = analyze_context(
            context, dev_assets, policy, output / "pairs/development", source, baseline
        )
        dev_rows.extend(rows)
        print(
            f"Development diagnosis {context['environment']}/{context['trajectory']}: {len(rows)} positive pairs",
            flush=True,
        )
    result = {
        "schema_version": 1,
        "artifact_root": str(output),
        "source_root": str(source),
        "source_test_results_sha256": sha256(source / "test-results.json"),
        "freeze_sha256": identity(frozen),
        "policy": policy,
        "minimum_correct_matches_per_pair": minimum,
        "baseline_event_hits": test["aggregate"]["baseline"]["usable_event_hits"],
        "reference_events": test["aggregate"]["baseline"]["events"],
        "events": event_results,
        "test_summary": summarize(test_rows, minimum),
        "development": {
            role: {
                "overall": summarize([r for r in dev_rows if r["split"] == role], minimum),
                "scenes": {
                    scene: summarize(
                        [r for r in dev_rows if r["split"] == role and r["environment"] == scene],
                        minimum,
                    )
                    for scene in sorted({r["environment"] for r in dev_rows})
                },
            }
            for role in settings["development_roles"]
        },
        "development_pairs": dev_rows,
        "model_changed": False,
        "reference_verdicts_changed": False,
        "test_role": "post_test_explanation_only",
    }
    write_json(output / "results.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("run", "check"), nargs="?", default="run")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    settings = yaml.safe_load(CONFIG.read_text())
    output = args.output or Path(settings["artifact_root"])
    output.mkdir(parents=True, exist_ok=True)
    if args.command == "check":
        result = load_json(output / "results.json")
        print(
            f"Baseline usable events: {result['baseline_event_hits']}/{result['reference_events']}"
        )
        raise SystemExit(0 if result["baseline_event_hits"] == result["reference_events"] else 2)
    result = run(settings, output)
    path = publish_report(
        {"sequence": "LDO matching failure diagnosis", "matching_diagnostics": result},
        ROOT / "evaluation/output",
        CONFIG,
    )
    write_json(output / "report.json", {"report": str(path), "sha256": sha256(path)})
    print(path, flush=True)


if __name__ == "__main__":
    main()
