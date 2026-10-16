"""Offline pose/feature diagnosis from immutable full-run evidence.

No inference, detector thresholds or XYZ verdicts are changed here.
"""

import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from uuid import uuid4

import numpy as np
import yaml

from loop_eval.tasks.feature_matching.xyz.poses import CameraPoses

from .comparison.reference import sha256
from .pose_assessment import assess_pose
from .statistical_geometry import pose_consistency

EVIDENCE_POLICY = {"minimum_judgeable": 8, "minimum_coverage": 0.4, "dominant_fraction": 0.8}


def distribution(values):
    values = np.asarray(values, dtype=float)
    if not values.size:
        return {
            "count": 0,
            "median": None,
            "p90": None,
            "p95": None,
            "maximum": None,
            "empirical_cdf": [],
        }
    if values.ndim != 1 or not np.isfinite(values).all() or np.any(values < 0):
        raise ValueError("Errors must be nonnegative finite scalars")
    unique, counts = np.unique(values, return_counts=True)
    return {
        "count": len(values),
        "median": float(np.median(values)),
        "p90": float(np.quantile(values, 0.90)),
        "p95": float(np.quantile(values, 0.95)),
        "maximum": float(values.max()),
        "empirical_cdf": [
            [float(v), float(c)]
            for v, c in zip(unique, np.cumsum(counts) / len(values), strict=True)
        ],
    }


def classify(row, policy):
    """Descriptive evidence grouping, not a causal verdict or a scene label."""
    pose = row["pose_assessment"]
    if not pose.get("available"):
        return "pose_unavailable"
    if pose["within_tolerance"]:
        return "pose_within_tolerance"
    counts = row["feature_counts"]
    judged = counts["supported"] + counts["contradicted"]
    reported = judged + counts["untestable"]
    sufficient = (
        judged >= policy["minimum_judgeable"]
        and reported > 0
        and judged / reported >= policy["minimum_coverage"]
    )
    if sufficient and counts["supported"] / judged >= policy["dominant_fraction"]:
        return "pose_failure_with_dominant_xyz_support"
    if sufficient and counts["contradicted"] / judged >= policy["dominant_fraction"]:
        return "pose_failure_with_dominant_xyz_contradiction"
    return "pose_failure_with_mixed_or_insufficient_xyz"


def attach_inlier_xyz(rows, records_by_id, config, expected_hashes):
    """Stream original feature evidence once, validating exact IDs and image hashes."""
    lookup = {(r["method"], r["query_timestamp_ns"], r["historical_timestamp_ns"]): r for r in rows}
    for name, settings in config["methods"].items():
        digest, seen = hashlib.sha256(), set()
        with (Path(settings["checks"]) / "pairs.jsonl").open("rb", buffering=1024 * 1024) as stream:
            for line in stream:
                digest.update(line)
                pair = json.loads(line)
                identity = (name, pair["query_timestamp_ns"], pair["historical_timestamp_ns"])
                if identity in seen:
                    raise ValueError("Duplicate original XYZ pair")
                seen.add(identity)
                if identity not in lookup:
                    raise ValueError("Original XYZ pair lacks an operational observation")
                row, record = lookup[identity], records_by_id[identity]
                for side in ("query", "historical"):
                    if (
                        pair["measurements"][f"{side}_image_sha256"]
                        != record[f"{side}_image_sha256"]
                    ):
                        raise ValueError("Original XYZ and operational image hashes differ")
                features = {}
                for feature in pair["stereo"]["feature_results"]:
                    key = (feature["query_feature_id"], feature["historical_feature_id"])
                    if key in features:
                        raise ValueError("Duplicate XYZ feature assignment")
                    if feature["verdict"] not in {"supported", "contradicted", "untestable"}:
                        raise ValueError("Unknown XYZ feature verdict")
                    features[key] = feature
                totals = Counter(f["verdict"] for f in features.values())
                if any(totals[k] != row["feature_counts"][k] for k in row["feature_counts"]):
                    raise ValueError("Original feature counts differ from audit")
                inliers = [tuple(key) for key in record["verification"]["inlier_assignment_ids"]]
                if len(set(inliers)) != len(inliers) or any(key not in features for key in inliers):
                    raise ValueError(
                        "PnP inliers do not identify unique reported XYZ correspondences"
                    )
                counts = Counter(features[key]["verdict"] for key in inliers)
                row["pnp_inlier_xyz_counts"] = {
                    k: counts[k] for k in ("supported", "contradicted", "untestable")
                }
                row["pnp_inlier_unknown_reasons"] = dict(
                    Counter(
                        features[key].get("reason", "unspecified")
                        for key in inliers
                        if features[key]["verdict"] == "untestable"
                    )
                )
                candidate = {**row, "feature_counts": row["pnp_inlier_xyz_counts"]}
                row["pnp_inlier_evidence_group"] = classify(candidate, EVIDENCE_POLICY)
        if digest.hexdigest() != expected_hashes[f"{name}_xyz"]:
            raise ValueError("Original XYZ evidence hash differs from frozen audit")
        if seen != {key for key in lookup if key[0] == name}:
            raise ValueError("Some operational pairs lack original XYZ evidence")


def risk_curve(rows, metric, higher_is_better):
    """Exploratory development curve over observable verifier quality; retain ties."""
    grouped, missing = {}, 0
    for row in rows:
        value = row["verification_diagnostics"].get(metric)
        if type(value) not in (int, float) or not math.isfinite(value):
            missing += 1
            continue
        grouped.setdefault(float(value), []).append(row)
    count, bad, points = 0, 0, []
    for threshold in sorted(grouped, reverse=higher_is_better):
        for row in grouped[threshold]:
            count += 1
            bad += not row["pose_assessment"]["within_tolerance"]
        points.append(
            {
                "threshold": threshold,
                "retained": count,
                "pose_inconsistent": bad,
                "pose_consistent": count - bad,
                "pose_error_rate": bad / count,
            }
        )
    return {
        "metric": metric,
        "direction": ">=" if higher_is_better else "<=",
        "missing_quality": missing,
        "points": points,
        "runtime_uses_ground_truth": False,
        "threshold_selection_status": "exploratory_not_frozen_or_held_out",
    }


def summarize(rows, assessment):
    accepted = [r for r in rows if r["status"] == "accepted"]
    judged = [r for r in accepted if r["pose_assessment"].get("available")]
    failures = [r for r in judged if not r["pose_assessment"]["within_tolerance"]]
    gate_counts = Counter()
    for row in failures:
        pose = row["pose_assessment"]
        t = pose["translation_error_m"] > assessment["maximum_translation_error_m"]
        r = pose["rotation_error_degrees"] > assessment["maximum_rotation_error_degrees"]
        gate_counts["both" if t and r else "translation_only" if t else "rotation_only"] += 1
    return {
        "candidates": len(rows),
        "accepted": len(accepted),
        "pose_judgeable": len(judged),
        "pose_unknown": len(accepted) - len(judged),
        "pose_inconsistent": len(failures),
        "pose_consistent": len(judged) - len(failures),
        "pose_error_rate_among_judgeable": len(failures) / len(judged) if judged else None,
        "failure_gates": dict(gate_counts),
        "failure_evidence": dict(Counter(r["evidence_group"] for r in failures)),
        "failure_pnp_inlier_evidence": dict(
            Counter(r.get("pnp_inlier_evidence_group", "not_supplied") for r in failures)
        ),
        "failure_pnp_inlier_xyz_totals": dict(
            sum((Counter(r.get("pnp_inlier_xyz_counts", {})) for r in failures), Counter())
        ),
        "failure_pnp_inlier_unknown_reasons": dict(
            sum((Counter(r.get("pnp_inlier_unknown_reasons", {})) for r in failures), Counter())
        ),
        "accepted_translation_error_m": distribution(
            [r["pose_assessment"]["translation_error_m"] for r in judged]
        ),
        "accepted_rotation_error_degrees": distribution(
            [r["pose_assessment"]["rotation_error_degrees"] for r in judged]
        ),
        "tolerance_sensitivity": [
            {
                "translation_m": t,
                "rotation_degrees": a,
                "within": sum(
                    r["pose_assessment"]["translation_error_m"] <= t
                    and r["pose_assessment"]["rotation_error_degrees"] <= a
                    for r in judged
                ),
                "denominator": len(judged),
            }
            for t in (0.1, 0.2, 0.5, 1.0)
            for a in (2.0, 5.0, 10.0)
        ],
        "development_quality_curves": [
            risk_curve(judged, key, higher)
            for key, higher in (
                ("inlier_ratio", True),
                ("median_error_px", False),
                ("pose_condition", False),
            )
        ],
    }


def diagnose(config, report_path):
    saved = json.loads(report_path.read_text(encoding="utf-8"))
    if saved.get("status") not in {"complete", "completed"}:
        raise ValueError("Diagnostics require a completed audit report")
    original = saved["comparison_result"]
    if original["protocol"] != config["protocol"]:
        raise ValueError("Diagnostics and audit protocols differ")
    verified = original["verified_connections"]
    scope = verified["scope"]
    if scope["fixed_pairs"] or scope["query_limit"] or scope["selected_reference_queries_only"]:
        raise ValueError("Diagnostics require full detector-candidate evidence")
    source = Path(verified["artifact_directory"]) / "pairs.jsonl"
    if sha256(source) != verified["pairs_sha256"]:
        raise ValueError("Operational evidence changed")
    manifest_path = Path(config["reference"]["root"]) / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if original["sequence"] != manifest["sequence"]:
        raise ValueError("Reference sequence mismatch")
    for filename, expected in manifest["reference_files"].items():
        if sha256(Path(filename)) != expected:
            raise ValueError("Ground truth or calibration changed")
    poses = CameraPoses(
        Path(config["reference"]["sequence"]), config["protocol"]["pose_tolerance_ms"]
    )
    with source.open(encoding="utf-8") as stream:
        records = [json.loads(line) for line in stream]

    def identity(r):
        return r["method"], r["query_timestamp_ns"], r["historical_timestamp_ns"]

    records_by_id = {identity(r): r for r in records}
    rows = original["verification_xyz_audit"]["rows"]
    if len(records_by_id) != len(records) or {identity(r) for r in rows} != set(records_by_id):
        raise ValueError("Audit and operational identities differ or duplicate")
    if len({identity(r) for r in rows}) != len(rows):
        raise ValueError("Duplicate audit row")
    output_rows = []
    for row in rows:
        record = records_by_id[identity(row)]
        if (
            row["status"] != record["verification"]["status"]
            or row["pose_assessment"] != record["pose_assessment"]
            or row["verification_diagnostics"] != record["verification"]["diagnostics"]
            or sum(row["feature_counts"].values())
            != record["verification"]["diagnostics"]["reported_matches"]
        ):
            raise ValueError("Audit measurements differ from operational evidence")
        row = dict(row)
        estimate = record["verification"].get("T_HQ")
        reference, _ = poses.relative(row["query_timestamp_ns"], row["historical_timestamp_ns"])
        recalculated = assess_pose(estimate, reference, verified["assessment_policy"])
        previous = row["pose_assessment"]
        if recalculated["available"] != previous["available"]:
            raise ValueError("Pose availability changed")
        if recalculated["available"]:
            for key in ("translation_error_m", "rotation_error_degrees"):
                if not math.isclose(recalculated[key], previous[key], rel_tol=1e-8, abs_tol=1e-8):
                    raise ValueError("Reference pose assessment changed")
            row["pose_statistics"] = pose_consistency(estimate, reference)
        else:
            row["pose_statistics"] = {
                "statistical_consistency": {
                    "available": False,
                    "reason": "pose_estimate_or_reference_missing",
                }
            }
        row["evidence_group"] = classify(row, EVIDENCE_POLICY)
        row["query_image_sha256"] = record["query_image_sha256"]
        row["historical_image_sha256"] = record["historical_image_sha256"]
        output_rows.append(row)
    attach_inlier_xyz(output_rows, records_by_id, config, original["source_sha256"])
    summaries = {
        name: summarize(
            [r for r in output_rows if r["method"] == name], verified["assessment_policy"]
        )
        for name in config["methods"]
    }
    for name, summary in summaries.items():
        if summary["accepted"] != verified["methods"][name]["accepted"]:
            raise ValueError("Accepted counts do not reconcile")
    split_path = Path(__file__).parent / "revisits/policy.yaml"
    split = yaml.safe_load(split_path.read_text(encoding="utf-8"))
    is_development = original["sequence"] in split["development_sequences"]
    if not is_development:
        for summary in summaries.values():
            summary["development_quality_curves"] = []
    target = summaries["orb"]["pose_error_rate_among_judgeable"] if is_development else None
    matched_risk = {}
    for name, summary in summaries.items():
        matched_risk[name] = {}
        for curve in summary["development_quality_curves"]:
            eligible = [
                p for p in curve["points"] if target is not None and p["pose_error_rate"] <= target
            ]
            best = max(eligible, key=lambda p: p["pose_consistent"], default=None)
            matched_risk[name][curve["metric"]] = best
    output = Path(config["output"]) / f"connection_diagnostics_{uuid4().hex}"
    output.mkdir(parents=True, exist_ok=False)
    failures = [
        r
        for r in output_rows
        if r["status"] == "accepted"
        and r["pose_assessment"].get("available")
        and not r["pose_assessment"]["within_tolerance"]
    ]
    failures.sort(
        key=lambda r: max(
            r["pose_assessment"]["translation_error_m"]
            / verified["assessment_policy"]["maximum_translation_error_m"],
            r["pose_assessment"]["rotation_error_degrees"]
            / verified["assessment_policy"]["maximum_rotation_error_degrees"],
        ),
        reverse=True,
    )
    failure_path = output / "accepted_pose_failures.jsonl"
    with failure_path.open("x", encoding="utf-8") as stream:
        for row in failures:
            stream.write(json.dumps(row, allow_nan=False) + "\n")
    csv_path = output / "candidates.csv"
    with csv_path.open("x", encoding="utf-8", newline="") as stream:
        fields = [
            "method",
            "query_timestamp_ns",
            "historical_timestamp_ns",
            "rank",
            "status",
            "translation_error_m",
            "rotation_error_degrees",
            "within_tolerance",
            "supported",
            "contradicted",
            "untestable",
            "evidence_group",
        ]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in output_rows:
            writer.writerow(
                {
                    **{k: row[k] for k in fields if k in row},
                    **row["feature_counts"],
                    **{
                        k: row["pose_assessment"].get(k)
                        for k in (
                            "translation_error_m",
                            "rotation_error_degrees",
                            "within_tolerance",
                        )
                    },
                }
            )
    return {
        "sequence": original["sequence"],
        "protocol": original["protocol"],
        "retrieval": {},
        "claim_validated": False,
        "claim_status": "Offline feature and pose diagnostics; real-revisit truth remains independent.",
        "source_sha256": {
            "audit_report": sha256(report_path),
            "development_split_policy": sha256(split_path),
            "operational_pairs": sha256(source),
            **{
                f"{name}_xyz": original["source_sha256"][f"{name}_xyz"]
                for name in config["methods"]
            },
            "diagnostics_code": sha256(Path(__file__)),
            "statistics_code": sha256(Path(__file__).with_name("statistical_geometry.py")),
        },
        "connection_diagnostics": {
            "methods": summaries,
            "assessment_policy": verified["assessment_policy"],
            "evidence_policy": EVIDENCE_POLICY,
            "exploratory_matched_pose_risk": {
                "target_orb_baseline_error_rate": target,
                "methods": matched_risk,
                "held_out_validated": False,
                "warning": "Post-hoc development selection only; freeze and independently test before claiming improvement.",
            },
            "rows": output_rows,
            "statistical_pose_verdict": {
                "available": False,
                "reason": "calibrated_joint_pose_covariance_not_recorded",
            },
            "scene_false_positives": {
                "available": False,
                "reason": "independent_scene_reference_not_supplied",
            },
            "artifacts": {
                "candidates_csv": str(csv_path),
                "accepted_failures_jsonl": str(failure_path),
            },
            "artifact_sha256": {
                "candidates_csv": sha256(csv_path),
                "accepted_failures_jsonl": sha256(failure_path),
            },
            "limitations": "Both all-match and exact PnP-inlier XYZ evidence are reported separately. Evidence groups suggest investigations, not proven causes. Risk curves are development diagnostics, not held-out performance or new gates.",
        },
    }


def render_diagnostics(task):
    lines = [
        "## Accepted connection diagnosis",
        "",
        "Outside tolerance means an inaccurate relative-pose estimate; it is not a proven false revisit.",
        "",
        "| Method | Accepted | GT-inconsistent | Error rate | Median translation (m) | P95 translation (m) | Median rotation (deg) | P95 rotation (deg) |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, m in task["methods"].items():
        t, a = m["accepted_translation_error_m"], m["accepted_rotation_error_degrees"]

        def fmt(v):
            return "Unavailable" if v is None else f"{v:.4f}"

        lines.append(
            f"| {name} | {m['accepted']} | {m['pose_inconsistent']} | {fmt(m['pose_error_rate_among_judgeable'])} | {fmt(t['median'])} | {fmt(t['p95'])} | {fmt(a['median'])} | {fmt(a['p95'])} |"
        )
    lines += [
        "",
        "### Failure evidence",
        "",
        "| Method | Translation only | Rotation only | Both | Dominant XYZ support | Dominant XYZ contradiction | Mixed / insufficient XYZ |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, m in task["methods"].items():
        gates, evidence = m["failure_gates"], m["failure_evidence"]
        lines.append(
            f"| {name} | {gates.get('translation_only', 0)} | {gates.get('rotation_only', 0)} | {gates.get('both', 0)} | {evidence.get('pose_failure_with_dominant_xyz_support', 0)} | {evidence.get('pose_failure_with_dominant_xyz_contradiction', 0)} | {evidence.get('pose_failure_with_mixed_or_insufficient_xyz', 0)} |"
        )
    lines += [
        "",
        "### XYZ evidence for PnP inliers in failed accepted poses",
        "",
        "| Method | Supported inliers | Contradicted inliers | Untestable inliers |",
        "| --- | ---: | ---: | ---: |",
    ]
    for name, m in task["methods"].items():
        counts = m["failure_pnp_inlier_xyz_totals"]
        lines.append(
            f"| {name} | {counts.get('supported', 0)} | {counts.get('contradicted', 0)} | {counts.get('untestable', 0)} |"
        )
    lines += [
        "",
        task["limitations"],
        "",
        "Complete candidate CSV, failure JSONL, empirical error CDFs, tolerance sensitivity and development quality/risk curves are saved with this report. Statistical pose verdicts are unavailable without calibrated residual covariance; scene false positives require independent scene labels.",
        "",
    ]
    return lines
