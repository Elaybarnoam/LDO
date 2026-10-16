"""Account for every abstention without changing feature verdicts.

Joint reason counts are exclusive per correspondence. Per-side counts and
reason incidences overlap and must not be interpreted as unique failures.
"""

from collections import Counter
from collections.abc import Iterable, Mapping


def empty_breakdown() -> dict:
    return {
        "untestable_reason_counts": {},
        "depth_failure_pair_counts": {},
        "depth_missing_side_counts": {},
        "query_depth_reason_counts": {},
        "historical_depth_reason_counts": {},
        "domain_verdict_counts": {},
    }


def summarize_coverage(features: Iterable[Mapping]) -> dict:
    counts = {name: Counter() for name in empty_breakdown()}
    for feature in features:
        qdomain, hdomain = (
            feature.get("query_primary_rectified_domain"),
            feature.get("historical_primary_rectified_domain"),
        )
        domain = (
            "unknown"
            if type(qdomain) is not bool or type(hdomain) is not bool
            else "primary_overlap"
            if qdomain and hdomain
            else "additional_field"
        )
        counts["domain_verdict_counts"][f"{domain}_{feature['verdict']}"] += 1
        for side in ("query", "historical"):
            counts[f"{side}_depth_reason_counts"][
                feature.get(f"{side}_depth_reason") or "reliable"
            ] += 1
        if feature["verdict"] != "untestable":
            continue
        query = feature.get("query_depth_reason")
        history = feature.get("historical_depth_reason")
        counts["untestable_reason_counts"][feature["reason"]] += 1
        pair = f"{query or 'reliable'} / {history or 'reliable'}"
        counts["depth_failure_pair_counts"][pair] += 1
        side = (
            "both"
            if query and history
            else "query_only"
            if query
            else "historical_only"
            if history
            else "other"
        )
        counts["depth_missing_side_counts"][side] += 1
    return {name: dict(sorted(value.items())) for name, value in counts.items()}


def merge_breakdown(target: dict, source: Mapping) -> None:
    """Merge bounded count records; reject negative or malformed IPC values."""
    if set(source) != set(empty_breakdown()):
        raise ValueError("Invalid evaluation coverage breakdown schema")
    for name, incoming in source.items():
        if not isinstance(incoming, Mapping) or any(
            not isinstance(reason, str) or type(count) is not int or count < 0
            for reason, count in incoming.items()
        ):
            raise ValueError("Invalid evaluation coverage breakdown counts")
        for reason, count in incoming.items():
            target[name][reason] = target[name].get(reason, 0) + count


def validate_breakdown(breakdown: Mapping, reported: int, untestable: int) -> None:
    for name in (
        "untestable_reason_counts",
        "depth_failure_pair_counts",
        "depth_missing_side_counts",
    ):
        if sum(breakdown[name].values()) != untestable:
            raise ValueError("Coverage failure reasons do not account for every untestable match")
    for name in ("query_depth_reason_counts", "historical_depth_reason_counts"):
        if sum(breakdown[name].values()) != reported:
            raise ValueError("Coverage side reasons do not account for every reported match")
    if sum(breakdown["domain_verdict_counts"].values()) != reported:
        raise ValueError("Coverage domains do not account for every reported match")
