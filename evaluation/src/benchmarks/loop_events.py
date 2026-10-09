"""Common measurement contract for baseline and model detector adapters."""

import math

PAIR_EVENTS = {"loop_proposed", "loop_verified", "loop_decision", "constraint_inserted",
               "map_merge_proposed", "map_merge_verified", "map_merge", "loop_candidate"}
QUERY_EVENTS = {"keyframe_created", "loop_query", "loop_retrieval"}


def normalize_loop_event(event_type: str, payload: dict, timestamp_ns: int,
                         detector_id: str) -> dict:
    """Validate measurements and attach stable source-image identities.

    Envelope.sequence_id + source timestamps identify the same image pair across
    detectors, regardless of native keyframe numbering or map corrections.
    This records detector decisions, never independent true/false-positive labels.
    """
    if event_type not in PAIR_EVENTS | QUERY_EVENTS:
        raise ValueError(f"Unsupported loop measurement: {event_type}")
    if type(timestamp_ns) is not int or timestamp_ns <= 0:
        raise ValueError("A positive integer source timestamp is required")
    if not isinstance(detector_id, str) or not detector_id:
        raise ValueError("detector_id is required")
    data = dict(payload)
    data.update(loop_contract_version=1, detector_id=detector_id)

    def integer(name, positive=False):
        value = data.get(name)
        if type(value) is not int or value < (1 if positive else 0):
            raise ValueError(f"{name} must be an {'positive' if positive else 'nonnegative'} integer")
        return value

    def images(stamp):
        return {camera: f"mav0/{camera}/data/{stamp}.png" for camera in ("cam0", "cam1")}

    if event_type in QUERY_EVENTS:
        for name in ("keyframe_id", "frame_id", "map_id"):
            integer(name)
        data["images"] = images(timestamp_ns)
        if event_type == "loop_query" and type(data.get("eligible")) is not bool:
            raise ValueError("loop_query requires explicit eligible boolean")
        if event_type == "loop_retrieval":
            for name in ("loop_candidates", "merge_candidates", "limit_per_kind"):
                integer(name)
        return data

    for prefix in ("query", "historical"):
        for suffix in ("keyframe_id", "frame_id", "map_id"):
            integer(f"{prefix}_{suffix}")
        stamp = integer(f"{prefix}_timestamp_ns", positive=True)
        data[f"{prefix}_images"] = images(stamp)
    if data["query_timestamp_ns"] != timestamp_ns:
        raise ValueError("Query timestamp differs from the event source timestamp")
    data["pair_id"] = f"{data['query_timestamp_ns']}:{data['historical_timestamp_ns']}"
    data["temporal_separation_ns"] = data["query_timestamp_ns"] - data["historical_timestamp_ns"]
    if event_type == "loop_candidate":
        for name in ("selection_stage", "selection_reason", "candidate_kind"):
            if not isinstance(data.get(name), str) or not data[name]:
                raise ValueError(f"Candidate selection requires {name}")
    if event_type.endswith(("_proposed", "_verified")):
        integer("attempt_id", positive=True)
        if not isinstance(data.get("stage"), str) or not data["stage"]:
            raise ValueError("A proposal/verification stage is required")
    if event_type.endswith("_verified") or event_type == "loop_decision":
        if type(data.get("accepted")) is not bool:
            raise ValueError("Decision requires explicit accepted boolean")
    if event_type.endswith("_verified"):
        duration = data.get("verification_seconds")
        if type(duration) not in (int, float) or not math.isfinite(duration) or duration < 0:
            raise ValueError("verification_seconds must be finite and nonnegative")
        if data.get("projection_matches") is not None:
            integer("projection_matches")
    return data
