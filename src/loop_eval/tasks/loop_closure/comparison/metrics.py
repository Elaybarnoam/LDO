"""Strict retrieval metrics: no unknown-as-negative or incomplete recall."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import numpy as np


def read_trace(path: Path, stamps: list[int], exclusion_ns: int, top_k: int) -> dict:
    queries = {}
    positions = {stamp: index for index, stamp in enumerate(stamps)}
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            record = json.loads(line)
            if "event_type" in record:
                if record["event_type"] != "retrieval_query":
                    continue
                record = record["payload"]
            query = record["query_timestamp_ns"]
            if type(query) is not int or query not in positions or query in queries:
                raise ValueError("Trace contains duplicate or unknown query")
            if positions[query] != len(queries):
                raise ValueError("Trace must cover the full replay chronologically")
            candidates = record["candidates"]
            if len(candidates) > top_k:
                raise ValueError("Trace exceeds frozen candidate budget")
            seen = set()
            for rank, candidate in enumerate(candidates, 1):
                historical = candidate["historical_timestamp_ns"]
                if (
                    type(historical) is not int
                    or historical not in positions
                    or query - historical < exclusion_ns
                    or historical in seen
                    or type(candidate["rank"]) is not int
                    or candidate["rank"] != rank
                ):
                    raise ValueError("Invalid candidate rank, history, exclusion or duplicate")
                seen.add(historical)
            expected = sum(query - h >= exclusion_ns for h in stamps[: positions[query]])
            if record.get("eligible_history_count") != expected:
                raise ValueError("Trace history policy differs from frozen protocol")
            queries[query] = candidates
    if len(queries) != len(stamps):
        raise ValueError("Incomplete detector trace")
    return queries


def retrieval_metrics(reference: dict, traces: dict, query_stamps: list[int], k: int) -> dict:
    by_query = {q: {} for q in query_stamps}
    for (q, h), item in reference.items():
        by_query[q][h] = item["label"]
    totals = Counter()
    per_query = []
    for query, labels in by_query.items():
        returned = [c["historical_timestamp_ns"] for c in traces[query][:k]]
        # Retain original ranks. Do not refill after reference admission exclusions.
        admitted = [h for h in returned if h in labels]
        counts = Counter(labels[h] for h in admitted)
        totals.update(counts)
        totals["excluded_missing_reference"] += len(returned) - len(admitted)
        positives = {h for h, label in labels.items() if label == "loop"}
        complete = bool(labels) and "unknown" not in labels.values()
        per_query.append(
            {
                "query_timestamp_ns": query,
                "complete": complete,
                "reference_positive_count": len(positives),
                "reference_negative_count": sum(label == "non_loop" for label in labels.values()),
                "returned": len(admitted),
                "true_positive": counts["loop"],
                "false_positive": counts["non_loop"],
                "unknown": counts["unknown"],
                "recall": counts["loop"] / len(positives) if complete and positives else None,
                "success": int(bool(positives.intersection(admitted)))
                if complete and positives
                else None,
            }
        )
    tp, fp, unknown = (totals[key] for key in ("loop", "non_loop", "unknown"))
    returned = tp + fp + unknown
    complete_rows = [row for row in per_query if row["complete"]]
    opportunities = [row for row in complete_rows if row["reference_positive_count"]]
    positive_count = sum(row["reference_positive_count"] for row in complete_rows)
    negative_count = sum(row["reference_negative_count"] for row in complete_rows)
    return {
        "k": k,
        "true_positive": tp,
        "false_positive": fp,
        "unknown": unknown,
        "excluded_missing_reference": totals["excluded_missing_reference"],
        "annotation_coverage_of_returns": (tp + fp) / returned if returned else None,
        "precision": tp / returned if returned and not unknown else None,
        "labeled_subset_precision_diagnostic": tp / (tp + fp) if tp + fp else None,
        "precision_lower_bound": tp / returned if returned else None,
        "precision_upper_bound": (tp + unknown) / returned if returned else None,
        "complete_queries": len(complete_rows),
        "selected_queries": len(query_stamps),
        "complete_query_fraction": len(complete_rows) / len(query_stamps) if query_stamps else None,
        "complete_query_pair_recall": sum(row["true_positive"] for row in complete_rows)
        / positive_count
        if positive_count
        else None,
        "complete_query_success": float(np.mean([row["success"] for row in opportunities]))
        if opportunities
        else None,
        "positive_complete_queries": len(opportunities),
        "complete_query_false_positive_rate": sum(row["false_positive"] for row in complete_rows)
        / negative_count
        if negative_count
        else None,
        "false_positive_per_selected_query": fp / len(query_stamps) if query_stamps else None,
        "per_query": per_query,
    }


def paired_interval(left: dict, right: dict, seed: int, block_size: int, samples: int) -> dict:
    """Paired block bootstrap for query success; incomplete queries never enter."""
    paired = list(zip(left["per_query"], right["per_query"], strict=True))
    if any(a["query_timestamp_ns"] != b["query_timestamp_ns"] for a, b in paired):
        raise ValueError("Bootstrap query order differs")
    blocks = [paired[i : i + block_size] for i in range(0, len(paired), block_size)]
    valid_blocks = [b for b in blocks if any(a["success"] is not None for a, _ in b)]
    if len(valid_blocks) < 2:
        return {
            "available": False,
            "reason": "Need at least two temporal blocks with labeled loop opportunities",
        }
    rng = np.random.default_rng(seed)
    estimates = []
    recall_differences, precision_differences = [], []

    def ratio(rows, method, denominator):
        selected = [pair[method] for pair in rows if pair[method].get("complete")]
        divisor = sum(row.get(denominator, 0) for row in selected)
        return sum(row["true_positive"] for row in selected) / divisor if divisor else None

    for _ in range(samples):
        drawn = [row for i in rng.integers(0, len(blocks), len(blocks)) for row in blocks[i]]
        differences = [b["success"] - a["success"] for a, b in drawn if a["success"] is not None]
        if differences:
            estimates.append(float(np.mean(differences)))
        for denominator, target in (
            ("reference_positive_count", recall_differences),
            ("returned", precision_differences),
        ):
            a, b = (ratio(drawn, method, denominator) for method in (0, 1))
            if a is not None and b is not None:
                target.append(b - a)
    differences = [b["success"] - a["success"] for a, b in paired if a["success"] is not None]
    return {
        "available": True,
        "metric": "LDO minus ORB complete-query success",
        "difference": float(np.mean(differences)),
        "interval_95": np.percentile(estimates, [2.5, 97.5]).tolist(),
        "seed": seed,
        "block_size_selected_queries": block_size,
        "samples": samples,
        "pair_recall_difference_interval_95": np.percentile(
            recall_differences, [2.5, 97.5]
        ).tolist()
        if recall_differences
        else None,
        "precision_difference_interval_95": np.percentile(
            precision_differences, [2.5, 97.5]
        ).tolist()
        if precision_differences
        else None,
        "scope": "Conditional within-sequence uncertainty; not cross-sequence generalization",
    }
