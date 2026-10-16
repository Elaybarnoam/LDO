"""Preliminary shared-pair gates; full event replay is required for promotion."""


def assess(old: dict, new: dict, settings: dict) -> dict:
    failures = []
    if set(old["scenes"]) != set(new["scenes"]):
        return {"passed": False, "failures": ["scenes_changed"]}
    for scene, baseline, candidate in [
        ("overall", old["overall"], new["overall"]),
        *((name, row, new["scenes"][name]) for name, row in old["scenes"].items()),
    ]:
        reasons = []
        if (
            candidate["pairs"] != baseline["pairs"]
            or candidate["positive_pairs"] != baseline["positive_pairs"]
        ):
            reasons.append("pair_population_changed")
        if (
            candidate["supported"]
            < settings["minimum_correct_match_retention"] * baseline["supported"]
        ):
            reasons.append("correct_match_retention_below_90_percent")
        if (
            candidate["usable_positive_pairs"]
            < settings["minimum_usable_pair_retention"] * baseline["usable_positive_pairs"]
        ):
            reasons.append("usable_positive_pair_retention_below_95_percent")
        for key in ("precision", "coverage"):
            if baseline[key] is not None and (
                candidate[key] is None or candidate[key] < baseline[key]
            ):
                reasons.append(f"{key}_decreased")
        failures.extend({"scope": scene, "reason": reason} for reason in reasons)
    if new["overall"]["contradicted"] >= old["overall"]["contradicted"]:
        failures.append({"scope": "overall", "reason": "incorrect_matches_not_reduced"})
    return {"passed": not failures, "failures": failures}
