"""Common image-retrieval contract for ORB and future transformer adapters."""

import math


def normalize_retrieval(payload, timestamp_ns, detector_id):
    if type(timestamp_ns) is not int or payload.get("query_timestamp_ns") != timestamp_ns:
        raise ValueError("Retrieval query timestamp mismatch")
    for field in ("eligible_history_count", "feature_count", "bow_word_count"):
        if type(payload.get(field)) is not int or payload[field] < 0:
            raise ValueError(f"Invalid {field}")
    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("Missing ranked candidates")
    seen, previous = set(), None
    for rank, candidate in enumerate(candidates, 1):
        stamp, score = candidate.get("historical_timestamp_ns"), candidate.get("score")
        if (
            candidate.get("rank") != rank
            or type(stamp) is not int
            or stamp >= timestamp_ns
            or stamp in seen
        ):
            raise ValueError("Invalid historical candidate/rank")
        cosine = payload.get("score_definition") == "cosine_similarity"
        valid_score = (
            type(score) in (int, float)
            and math.isfinite(score)
            and (-1 <= score <= 1 if cosine else 0 < score <= 1)
        )
        if not valid_score:
            raise ValueError("Invalid normalized similarity score")
        order = (-score, stamp)
        if previous is not None and order < previous:
            raise ValueError("Candidates must be sorted by descending score, then oldest timestamp")
        seen.add(stamp)
        previous = order
    timings = payload.get("timings_ms")
    if not isinstance(timings, dict) or not timings:
        raise ValueError("Missing retrieval timings")
    for value in timings.values():
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError("Invalid retrieval timing")
    return {**payload, "detector_id": detector_id, "measurement": "ranked_retrieval"}
