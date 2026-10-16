"""Admission rules for subsequent matching experiments, using external metrics."""


def assess_promotion(baseline: dict, candidate: dict) -> dict:
    """Require fewer contradictions and preserve every baseline usable event.

    Call this separately on full development fit and validation replays. Inputs
    must include event IDs, not just counts; swapping one event for another is a
    regression. This function belongs to evaluation and is never a model policy.
    """
    failures = []
    if baseline["protocol_sha256"] != candidate["protocol_sha256"]:
        failures.append("protocol_changed")
    if baseline["query_count"] != candidate["query_count"]:
        failures.append("replay_incomplete")
    if set(baseline["scenes"]) != set(candidate["scenes"]):
        failures.append("scenes_changed")
    else:
        for scene, original in baseline["scenes"].items():
            proposed = candidate["scenes"][scene]
            lost = sorted(set(original["usable_event_ids"]) - set(proposed["usable_event_ids"]))
            if lost:
                failures.append({"scene": scene, "lost_usable_event_ids": lost})
            if proposed["correct_matches"] < 0.9 * original["correct_matches"]:
                failures.append(
                    {"scene": scene, "reason": "correct_match_retention_below_90_percent"}
                )
    if candidate["incorrect_matches"] >= baseline["incorrect_matches"]:
        failures.append("incorrect_matches_not_reduced")
    return {"eligible": not failures, "failures": failures}
