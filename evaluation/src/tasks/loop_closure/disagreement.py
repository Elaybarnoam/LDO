"""Read-only audit joining external feature truth to operational verification."""

import json
from collections import Counter
from pathlib import Path

from .comparison.comparison import feature_profile, summarize_features
from .comparison.reference import sha256

STATUSES = ("accepted", "rejected", "insufficient_evidence")
HIGHLIGHT = {
    "minimum_supported": 8,
    "minimum_judgeable_support_ratio": 0.8,
    "minimum_coverage": 0.4,
}


def join_evidence(profiles: dict, records: list[dict]) -> dict:
    seen, rows, grouped = set(), [], {name: {s: {} for s in STATUSES} for name in profiles}
    for record in records:
        name = record["method"]
        pair = (record["query_timestamp_ns"], record["historical_timestamp_ns"])
        identity = (name, *pair)
        if identity in seen:
            raise ValueError("Duplicate operational pair")
        seen.add(identity)
        evidence = profiles[name]["pairs"].get(pair)
        if evidence is None:
            raise ValueError("Operational pair missing from unfiltered external XYZ evidence")
        if evidence["images"] != [
            record[f"{side}_image_sha256"] for side in ("query", "historical")
        ]:
            raise ValueError("Operational and external XYZ images differ")
        counts = evidence["counts"]
        reported = sum(counts.values())
        if reported != record["verification"]["diagnostics"]["reported_matches"]:
            raise ValueError("Operational and XYZ reported assignment counts differ")
        status = record["verification"]["status"]
        if status not in STATUSES:
            raise ValueError("Unknown operational status")
        grouped[name][status][pair] = evidence
        judged = counts["supported"] + counts["contradicted"]
        coverage = judged / reported if reported else None
        support_ratio = counts["supported"] / judged if judged else None
        highlight = (
            counts["supported"] >= HIGHLIGHT["minimum_supported"]
            and support_ratio is not None
            and support_ratio >= HIGHLIGHT["minimum_judgeable_support_ratio"]
            and coverage is not None
            and coverage >= HIGHLIGHT["minimum_coverage"]
        )
        rows.append(
            {
                "method": name,
                "query_timestamp_ns": pair[0],
                "historical_timestamp_ns": pair[1],
                "rank": record["rank"],
                "status": status,
                "reason": record["verification"]["reason"],
                "feature_counts": counts,
                "coverage": coverage,
                "support_among_judgeable": support_ratio,
                "strong_xyz_support": highlight,
                "pose_assessment": record["pose_assessment"],
                "verification_diagnostics": record["verification"]["diagnostics"],
            }
        )
    return {
        "highlight_policy": HIGHLIGHT,
        "highlight_is_operational_gate": False,
        "rows": rows,
        "methods": {
            name: {
                "all_external_pairs": len(profile["pairs"]),
                "external_pairs_without_operational_record": len(profile["pairs"])
                - sum(len(p) for p in grouped[name].values()),
                "by_operational_status": {
                    s: summarize_features(p) for s, p in grouped[name].items()
                },
                "strong_support_by_status": dict(
                    Counter(
                        r["status"] for r in rows if r["method"] == name and r["strong_xyz_support"]
                    )
                ),
            }
            for name, profile in profiles.items()
        },
    }


def audit(config: dict, verification_report: Path) -> dict:
    saved = json.loads(verification_report.read_text(encoding="utf-8"))
    if saved.get("status") not in {"complete", "completed"}:
        raise ValueError("Audit requires a completed verification report")
    original = saved["comparison_result"]
    if original["protocol"] != config["protocol"]:
        raise ValueError("Audit and verification protocols differ")
    verified = original["verified_connections"]
    if verified["scope"]["fixed_pairs"]:
        raise ValueError(
            "Use matching-specific XYZ paths for a fixed-pair audit; default audit requires detector candidates"
        )
    pairs_path = Path(verified["artifact_directory"]) / "pairs.jsonl"
    if sha256(pairs_path) != verified["pairs_sha256"]:
        raise ValueError("Operational evidence hash changed")
    profiles = {
        name: feature_profile(Path(paths["checks"])) for name, paths in config["methods"].items()
    }
    if profiles["orb"]["policy"] != profiles["ldo"]["policy"]:
        raise ValueError("External XYZ policies differ")
    hashes = [
        {
            Path(p).name: v
            for p, v in profile["provenance"]["input_and_code_sha256"].items()
            if Path(p).name == "xyz.py"
        }
        for profile in profiles.values()
    ]
    if not hashes[0] or hashes[0] != hashes[1]:
        raise ValueError("External XYZ numerical implementations differ")
    with pairs_path.open(encoding="utf-8") as stream:
        records = [json.loads(line) for line in stream]
    joined = join_evidence(profiles, records)
    for name, method in joined["methods"].items():
        for status, group in method["by_operational_status"].items():
            if group["pairs"] != verified["methods"][name][status]:
                raise ValueError("Joined operational counts do not reconcile")
    return {
        "sequence": original["sequence"],
        "protocol": original["protocol"],
        "retrieval": {},
        "claim_validated": False,
        "claim_status": "Primary feature evaluation is unfiltered; operational verification is a separate secondary experiment.",
        "source_sha256": {
            "audit_implementation": sha256(Path(__file__)),
            "verification_report": sha256(verification_report),
            "operational_pairs": sha256(pairs_path),
            **{f"{name}_xyz": profile["source_hash"] for name, profile in profiles.items()},
        },
        "features": {
            "mode": "all_reported_candidates_no_operational_filter",
            "shared_pairs": len(set(profiles["orb"]["pairs"]) & set(profiles["ldo"]["pairs"])),
            "all_pairs": {name: summarize_features(p["pairs"]) for name, p in profiles.items()},
            "warning": "Different candidate sets. All external XYZ matches remain included regardless of operational acceptance; untestable is not incorrect.",
        },
        "verified_connections": verified,
        "verification_xyz_audit": joined,
    }
