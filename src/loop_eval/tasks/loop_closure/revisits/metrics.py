"""Distinct revisit events and conservative independent-reference metrics."""

from collections import Counter, defaultdict

import numpy as np


def build_events(reference: dict, queries: list[int], maximum_gap_ns: int) -> list[dict]:
    positive = defaultdict(list)
    for (q, h), item in reference.items():
        if item["label"] == "loop":
            positive[q].append(h)
    events, current = [], None
    for q in queries:
        if q not in positive:
            current = None  # Unknown/negative queries cannot bridge confirmed events.
            continue
        if current is None or q - current["query_timestamps"][-1] > maximum_gap_ns:
            current = {
                "event_id": f"revisit_{q}",
                "query_timestamps": [],
                "historical_by_query": {},
            }
            events.append(current)
        current["query_timestamps"].append(q)
        current["historical_by_query"][str(q)] = sorted(positive[q])
    for event in events:
        event["start_ns"], event["end_ns"] = (
            event["query_timestamps"][0],
            event["query_timestamps"][-1],
        )
    return events


def evaluate(
    reference: dict,
    traces: dict,
    queries: list[int],
    events: list[dict],
    k: int,
    threshold: float | None = None,
    accepted: set | None = None,
) -> dict:
    by_query = defaultdict(dict)
    for (q, h), row in reference.items():
        by_query[q][h] = row["label"]
    eligible_queries = [q for q in queries if by_query[q]]
    counts, hits, per_query = Counter(), set(), []
    for q in eligible_queries:
        selected = traces[q][:k]
        if threshold is not None:
            selected = [c for c in selected if c["score"] >= threshold]
        if accepted is not None:
            selected = [c for c in selected if (q, c["historical_timestamp_ns"]) in accepted]
        labels = by_query[q]
        returned = [c["historical_timestamp_ns"] for c in selected]
        admitted = [h for h in returned if h in labels]
        local = Counter(labels[h] for h in admitted)
        counts.update(local)
        counts["excluded_missing_pose"] += len(returned) - len(admitted)
        correct = {h for h in admitted if labels[h] == "loop"}
        hits.update((q, h) for h in correct)
        positives = {h for h, label in labels.items() if label == "loop"}
        complete = "unknown" not in labels.values()
        per_query.append(
            {
                "query_timestamp_ns": q,
                "complete": complete,
                "positive": bool(positives),
                "success": int(bool(correct)) if complete and positives else None,
                "true_positive": local["loop"],
                "false_positive": local["non_loop"],
                "unknown": local["unknown"],
                "returned": len(admitted),
            }
        )
    outcomes = []
    for event in events:
        successful_queries = [
            q
            for q in event["query_timestamps"]
            if any((q, h) in hits for h in event["historical_by_query"][str(q)])
        ]
        outcomes.append(
            {
                "event_id": event["event_id"],
                "detected": bool(successful_queries),
                "successful_queries": len(successful_queries),
                "query_frames": len(event["query_timestamps"]),
                "first_detection_delay_s": (successful_queries[0] - event["start_ns"]) / 1e9
                if successful_queries
                else None,
            }
        )
    tp, fp, unknown = (counts[key] for key in ("loop", "non_loop", "unknown"))
    total = tp + fp + unknown
    complete = bool(eligible_queries) and all(row["complete"] for row in per_query)
    detected = sum(row["detected"] for row in outcomes)
    complete_positive = [row for row in per_query if row["complete"] and row["positive"]]
    return {
        "k": k,
        "score_threshold": threshold,
        "true_positive_pairs": tp,
        "false_positive_pairs": fp,
        "unknown_pairs": unknown,
        "returned_pairs": total,
        "excluded_missing_pose": counts["excluded_missing_pose"],
        "precision": tp / total if total and not unknown else None,
        "precision_lower_bound": tp / total if total else None,
        "precision_upper_bound": (tp + unknown) / total if total else None,
        "annotation_coverage_of_returns": (tp + fp) / total if total else None,
        "reference_complete": complete,
        "eligible_queries": len(eligible_queries),
        "complete_queries": sum(row["complete"] for row in per_query),
        "confirmed_events": len(events),
        "detected_confirmed_events": detected,
        "missed_confirmed_events": len(events) - detected,
        "event_recall": detected / len(events) if complete and events else None,
        "known_event_recall_diagnostic": detected / len(events) if events else None,
        "complete_query_success_diagnostic": float(
            np.mean([row["success"] for row in complete_positive])
        )
        if complete_positive
        else None,
        "per_query": per_query,
        "per_event": outcomes,
    }


def paired_event_uncertainty(
    left: dict, right: dict, seed: int, block_size: int, samples: int
) -> dict:
    if not left["reference_complete"] or not right["reference_complete"]:
        return {"available": False, "reason": "Independent event reference is incomplete"}
    a, b = left["per_event"], right["per_event"]
    if [r["event_id"] for r in a] != [r["event_id"] for r in b]:
        raise ValueError("Paired event identities differ")
    differences = [int(y["detected"]) - int(x["detected"]) for x, y in zip(a, b, strict=True)]
    blocks = [differences[i : i + block_size] for i in range(0, len(differences), block_size)]
    if len(blocks) < 2:
        return {"available": False, "reason": "Need at least two temporal event blocks"}
    rng = np.random.default_rng(seed)
    estimates = [
        float(np.mean([d for i in rng.integers(0, len(blocks), len(blocks)) for d in blocks[i]]))
        for _ in range(samples)
    ]
    return {
        "available": True,
        "metric": "LDO minus ORB event recall",
        "difference": float(np.mean(differences)),
        "interval_95": np.percentile(estimates, [2.5, 97.5]).tolist(),
        "seed": seed,
        "block_size_events": block_size,
        "samples": samples,
        "scope": "Within-sequence temporal-event uncertainty; not cross-sequence generalization",
    }
