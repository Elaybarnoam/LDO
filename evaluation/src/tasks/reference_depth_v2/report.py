"""Human-readable before/after evaluator results with abstentions and transitions."""


def percent(value):
    return "Unavailable" if value is None else f"{value:.1%}"


def rates(counts):
    judged = counts["supported"] + counts["contradicted"]
    total = judged + counts["untestable"]
    return percent(judged / total if total else None), percent(
        counts["supported"] / judged if judged else None
    )


def render(result):
    rows = [(e["environment"], e["methods"]) for e in result["environments"]] + [
        ("Combined", result["aggregate"])
    ]
    lines = [
        "# TartanAir reference-depth evaluator v2",
        "",
        "Same saved ORB and LDO correspondences, new independent evaluator. No detector inference or matching was rerun. Original results are preserved. Candidate labels and event-hit counts are unchanged.",
        "",
        "Valid positive finite non-sky depths have no metric distance cutoff. Sky is excluded using official semantic masks. Inverse depth is interpolated within the active subpixel footprint only; mixed-depth footprints remain unknown. XYZ and symmetric reprojection tolerances are unchanged.",
        "",
        "## Feature results before and after",
        "",
        "| Environment | Detector | Evaluator | Correct | Incorrect | Unknown | Judgeable coverage | Correct among judgeable |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, methods in rows:
        for method, stats in methods.items():
            for version in ("old", "new"):
                r = stats[version]
                coverage, precision = rates(r)
                lines.append(
                    f"| {name} | {method} | {version} | {r['supported']} | {r['contradicted']} | {r['untestable']} | {coverage} | {precision} |"
                )
    lines += [
        "",
        "## Verdict transitions",
        "",
        "| Environment | Detector | Transition | Matches |",
        "| --- | --- | --- | ---: |",
    ]
    for name, methods in rows:
        for method, stats in methods.items():
            for transition, count in sorted(stats["transitions"].items()):
                lines.append(f"| {name} | {method} | {transition} | {count} |")
    lines += [
        "",
        "## Remaining unknown evidence",
        "",
        "One primary reason per match, with invalid pixels/depth, sky and unmapped semantics taking precedence over boundary ambiguity.",
        "",
        "| Environment | Detector | Reason | Matches |",
        "| --- | --- | --- | ---: |",
    ]
    for name, methods in rows:
        for method, stats in methods.items():
            for reason, count in sorted(stats["unknown_reasons"].items()):
                lines.append(f"| {name} | {method} | {reason} | {count} |")
    lines += [
        "",
        "## Distance breakdown",
        "",
        "Distance is the maximum sampled axial depth at the two endpoints. Unusable endpoints appear in unknown_depth.",
        "",
        "| Environment | Detector | Distance | Correct | Incorrect | Unknown |",
        "| --- | --- | --- | ---: | ---: | ---: |",
    ]
    for name, methods in rows:
        for method, stats in methods.items():
            for bucket, counts in stats["distance_bins"].items():
                lines.append(
                    f"| {name} | {method} | {bucket} | {counts['supported']} | {counts['contradicted']} | {counts['untestable']} |"
                )
    lines += [
        "",
        "## Interpretation",
        "",
        "- This evaluator revision follows inspection of these test results; it is not fresh held-out evidence or model optimization.",
        "- More judged matches can be correct or incorrect. Sampling changes can revise earlier known verdicts; inspect the transition table.",
        "- Semantic labels identify sky, not trustworthy depth on every other object. Reflective, transparent, rendered background and boundary surfaces can still limit physical interpretation.",
        "- The unchanged tolerances are operational criteria, not calibrated uncertainty probabilities. Controlled cases test implementation behavior; they do not prove every real correspondence label.",
        "- Unknowns are not false positives. Feature precision is conditional on judgeable evidence, not accepted loop-closure accuracy.",
        "- Image-pair overlap labels were not recomputed, so the original candidate/event results remain under the original depth policy.",
        "- Original EuRoC XYZ and frozen TartanAir evaluators remain unchanged.",
        "",
        "## Provenance",
        "",
        f"Source results SHA256: `{result['source_results_sha256']}`",
        "",
        f"Configuration SHA256: `{result['configuration_sha256']}`",
        "",
        "Per-feature compressed evidence, semantic-mask hashes and code snapshots are recorded in the accompanying JSON report.",
        "",
    ]
    return "\n".join(lines)
