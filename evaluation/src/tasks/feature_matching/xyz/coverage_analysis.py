"""Stream a completed feature evaluation into an auditable coverage profile.

Run with ``python -m tasks.feature_matching.xyz.coverage_analysis --checks DIR
--output FILE.json``. This reads evidence only; it never reclassifies features.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from .coverage import empty_breakdown, merge_breakdown, summarize_coverage, validate_breakdown


def analyze_checks(checks: Path) -> dict:
    summary = json.loads((checks / "summary.json").read_text())
    if summary.get("complete") is not True:
        raise ValueError("Coverage analysis requires a completed evaluation")
    breakdown = empty_breakdown()
    verdicts = Counter()
    observations: dict[tuple[int, int], str] = {}
    pair_counts = []
    digest = hashlib.sha256()
    with (checks / "pairs.jsonl").open("rb") as stream:
        for line in stream:
            digest.update(line)
            pair = json.loads(line)
            features = pair["stereo"]["feature_results"]
            merge_breakdown(breakdown, summarize_coverage(features))
            counts = Counter(feature["verdict"] for feature in features)
            verdicts.update(counts)
            pair_counts.append(
                {
                    "query_timestamp_ns": pair["query_timestamp_ns"],
                    "historical_timestamp_ns": pair["historical_timestamp_ns"],
                    "reported": len(features),
                    "testable": counts["supported"] + counts["contradicted"],
                }
            )
            for feature in features:
                for side in ("query", "historical"):
                    key = (feature[f"{side}_timestamp_ns"], feature[f"{side}_feature_id"])
                    reason = feature.get(f"{side}_depth_reason") or "reliable"
                    if key in observations and observations[key] != reason:
                        raise ValueError("Same saved observation has inconsistent depth evidence")
                    observations[key] = reason
    verdicts = {name: verdicts[name] for name in ("supported", "contradicted", "untestable")}
    if verdicts != summary["feature_totals"] or len(pair_counts) != summary["checked_pairs"]:
        raise ValueError("Coverage evidence does not match completed summary")
    reported = sum(verdicts.values())
    testable = verdicts["supported"] + verdicts["contradicted"]
    validate_breakdown(breakdown, reported, verdicts["untestable"])
    incidence = Counter()
    for reasons, count in breakdown["depth_failure_pair_counts"].items():
        for reason in set(reasons.split(" / ")) - {"reliable"}:
            incidence[reason] += count
    return {
        "source": str(checks),
        "pairs_sha256": digest.hexdigest(),
        "feature_totals": verdicts,
        "coverage": testable / reported if reported else None,
        "coverage_breakdown": breakdown,
        "untestable_reason_incidence": dict(incidence),
        "incidence_counts_overlap": True,
        "unique_frame_feature_observations": len(observations),
        "unique_observation_depth_reasons": dict(Counter(observations.values())),
        "unique_observations_are_not_unique_world_landmarks": True,
        "pair_counts": pair_counts,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checks", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = analyze_checks(args.checks)
    with args.output.open("x", encoding="utf-8") as destination:
        json.dump(result, destination, indent=2, allow_nan=False)
        destination.write("\n")
    print(f"Coverage: {result['coverage']}; report: {args.output}")


if __name__ == "__main__":
    main()
