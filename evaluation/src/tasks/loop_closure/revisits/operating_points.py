"""Select thresholds only on complete development references, then freeze them."""

import math

from .metrics import evaluate


def select(reference, traces, queries, events, k, target_precision):
    base = evaluate(reference, traces, queries, events, k)
    if not base["reference_complete"]:
        return {"available": False, "reason": "Independent development reference is incomplete"}
    event_by_pair = {
        (q, h): event["event_id"]
        for event in events
        for q in event["query_timestamps"]
        for h in event["historical_by_query"][str(q)]
    }
    grouped = {}
    for q in queries:
        for candidate in traces[q][:k]:
            score = float(candidate["score"])
            if not math.isfinite(score):
                raise ValueError("Nonfinite retrieval score")
            pair = (q, candidate["historical_timestamp_ns"])
            if pair in reference:
                grouped.setdefault(score, []).append(pair)
    tp, fp, found, points = 0, 0, set(), []
    for score in sorted(grouped, reverse=True):
        for pair in grouped[score]:
            if reference[pair]["label"] == "loop":
                tp += 1
                found.add(event_by_pair[pair])
            else:
                fp += 1
        points.append(
            {
                "score_threshold": score,
                "precision": tp / (tp + fp),
                "event_recall": len(found) / len(events) if events else None,
                "returned_pairs": tp + fp,
            }
        )
    usable = [
        p
        for p in points
        if p["precision"] is not None
        and p["precision"] >= target_precision
        and p["event_recall"] is not None
    ]
    if not usable:
        return {
            "available": False,
            "reason": "No scored operating point meets the target with labeled revisit events",
        }
    best = max(
        usable, key=lambda p: (p["event_recall"], p["returned_pairs"], -p["score_threshold"])
    )
    return {
        "available": True,
        "score_threshold": best["score_threshold"],
        "target_precision": target_precision,
        "development_precision": best["precision"],
        "development_event_recall": best["event_recall"],
        "k": k,
        "score_direction": "higher_is_more_similar",
        "sweep": [
            {
                key: p[key]
                for key in ("score_threshold", "precision", "event_recall", "returned_pairs")
            }
            for p in points
        ],
    }


def check_frozen_operating_points(artifact, sequence, policy, protocol, fingerprints):
    if artifact.get("version") != 1 or artifact.get("available") is not True:
        raise ValueError("Frozen operating points are unavailable")
    if sequence in policy["development_sequences"] or sequence == artifact["development_sequence"]:
        raise ValueError("Held-out operating points cannot be evaluated on development data")
    if sequence not in policy["held_out_sequences"]:
        raise ValueError("Sequence is not in the frozen held-out split")
    if (
        artifact["policy"] != policy
        or artifact["protocol"] != protocol
        or artifact["configuration_fingerprints"] != fingerprints
    ):
        raise ValueError("Frozen settings/model configuration differ")
    for methods in artifact["points"].values():
        for point in methods.values():
            if point.get("available") is not True or not math.isfinite(point["score_threshold"]):
                raise ValueError("Invalid frozen score threshold")
