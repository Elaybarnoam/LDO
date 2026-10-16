"""Promotion gates operate on cumulative baseline retention, never test outcomes."""

from collections import Counter


def summarize(rows, minimum_matches):
    counts = Counter({k: 0 for k in ("supported", "contradicted", "untestable")})
    categories = {}
    positives, usable = 0, 0
    for row in rows:
        counts.update(row["counts"])
        label = row["label"]
        categories.setdefault(label, Counter()).update(row["counts"])
        positives += label == "loop"
        usable += label == "loop" and row["counts"]["supported"] >= minimum_matches
    judged = counts["supported"] + counts["contradicted"]
    total = sum(counts.values())
    return {
        **dict(counts),
        "pairs": len(rows),
        "positive_pairs": positives,
        "usable_positive_pairs": usable,
        "precision": counts["supported"] / judged if judged else None,
        "coverage": judged / total if total else None,
        "by_pair_label": {k: dict(v) for k, v in categories.items()},
    }


def measure(rows, minimum_matches):
    return {
        "overall": summarize(rows, minimum_matches),
        "scenes": {
            name: summarize([r for r in rows if r["environment"] == name], minimum_matches)
            for name in sorted({r["environment"] for r in rows})
        },
    }


def eligible(baseline, candidate, policy):
    scopes = [(baseline["overall"], candidate["overall"])]
    if set(baseline["scenes"]) != set(candidate["scenes"]):
        return False
    scopes += [(r, candidate["scenes"][name]) for name, r in baseline["scenes"].items()]
    for old, new in scopes:
        if old["pairs"] != new["pairs"] or old["positive_pairs"] != new["positive_pairs"]:
            return False
        if new["supported"] < policy["minimum_correct_match_retention"] * old["supported"]:
            return False
        if (
            new["usable_positive_pairs"]
            < policy["minimum_usable_pair_retention"] * old["usable_positive_pairs"]
        ):
            return False
        if old["precision"] is not None and (
            new["precision"] is None or new["precision"] < old["precision"]
        ):
            return False
    return True


def choose(candidates, baseline, previous, policy):
    feasible = [
        r
        for r in candidates
        if eligible(baseline, r["fit"], policy)
        and r["fit"]["overall"]["contradicted"] < previous["fit"]["overall"]["contradicted"]
    ]
    return (
        min(
            feasible,
            key=lambda r: (
                r["fit"]["overall"]["contradicted"],
                -r["fit"]["overall"]["supported"],
                r["id"],
            ),
        )
        if feasible
        else previous
    )
