"""Accepted-connection accuracy stays separate from operational acceptance."""

from collections import Counter

import numpy as np


def summarize_connections(records: list[dict]) -> dict:
    states, outcomes, reasons = Counter(), Counter(), Counter()
    errors = []
    for item in records:
        states[item["verification"]["status"]] += 1
        reasons[item["verification"]["reason"]] += 1
        if item["verification"]["status"] == "accepted":
            label, pose = item["reference_label"], item["pose_assessment"]
            if label == "unknown" or not pose["available"]:
                outcomes["unresolved"] += 1
            elif label == "non_loop":
                outcomes["incorrect_pair"] += 1
            elif not pose["within_tolerance"]:
                outcomes["incorrect_pose"] += 1
            else:
                outcomes["correct"] += 1
        pose = item["pose_assessment"]
        if pose["available"]:
            errors.append((pose["translation_error_m"], pose["rotation_error_degrees"]))
    accepted = states["accepted"]
    wrong = outcomes["incorrect_pair"] + outcomes["incorrect_pose"]
    return {
        "pairs": len(records),
        "accepted": accepted,
        "rejected": states["rejected"],
        "insufficient_evidence": states["insufficient_evidence"],
        "correct_accepted": outcomes["correct"],
        "incorrect_accepted": wrong,
        "incorrect_pair_accepted": outcomes["incorrect_pair"],
        "incorrect_pose_accepted": outcomes["incorrect_pose"],
        "unresolved_accepted": outcomes["unresolved"],
        "precision": outcomes["correct"] / accepted
        if accepted and not outcomes["unresolved"]
        else None,
        "precision_lower_bound": outcomes["correct"] / accepted if accepted else None,
        "precision_upper_bound": (outcomes["correct"] + outcomes["unresolved"]) / accepted
        if accepted
        else None,
        "median_translation_error_m": float(np.median([e[0] for e in errors])) if errors else None,
        "median_rotation_error_degrees": float(np.median([e[1] for e in errors]))
        if errors
        else None,
        "reason_counts": dict(reasons),
    }


def query_outcomes(reference: dict, records: list[dict], processed_queries: list[int], k: int):
    per_query = []
    indexed = {
        (r["query_timestamp_ns"], r["historical_timestamp_ns"]): r
        for r in records
        if r["rank"] <= k
    }
    for q in processed_queries:
        labels = {h: r["label"] for (query, h), r in reference.items() if query == q}
        complete = bool(labels) and "unknown" not in labels.values()
        positives = {h for h, label in labels.items() if label == "loop"}
        found, misses = 0, Counter()
        for h in positives:
            item = indexed.get((q, h))
            if item is None:
                misses["not_retrieved"] += 1
            elif item["verification"]["status"] != "accepted":
                misses[item["verification"]["status"]] += 1
            elif not item["pose_assessment"].get("within_tolerance", False):
                misses["inaccurate_or_unassessed_pose"] += 1
            else:
                found += 1
        rows = [r for (query, _), r in indexed.items() if query == q]
        accepted = [r for r in rows if r["verification"]["status"] == "accepted"]
        per_query.append(
            {
                "query_timestamp_ns": q,
                "complete": complete,
                "reference_positive_count": len(positives),
                "true_positive": found,
                "returned": len(accepted),
                "success": int(found > 0) if complete and positives else None,
                "miss_reasons": dict(misses) if complete else {},
                "recall": found / len(positives) if complete and positives else None,
            }
        )
    available = [r for r in per_query if r["complete"] and r["reference_positive_count"]]
    denominator = sum(r["reference_positive_count"] for r in available)
    return {
        "k": k,
        "complete_queries": sum(r["complete"] for r in per_query),
        "selected_queries": len(per_query),
        "per_query": per_query,
        "pair_recall": sum(r["true_positive"] for r in available) / denominator
        if denominator
        else None,
        "query_success": float(np.mean([r["success"] for r in available])) if available else None,
    }
