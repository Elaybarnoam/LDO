"""Report every matching ablation and its promotion decision, including failures."""


def pct(value):
    return "Unavailable" if value is None else f"{value:.1%}"


def render(result):
    development = result["development"]
    lines = [
        "# LDO feature matching optimization",
        "",
        "Identical fixed image pairs, pretrained weights and unchanged independent depth-v2 evaluation. Previously inspected factory/desert scenes are development data; no new unseen claim is made for them.",
        "",
        "## Sequential decisions",
        "",
        "| Step | Fit-selected configuration | Promoted on validation | Kept configuration |",
        "| --- | --- | --- | --- |",
    ]
    for step in development["steps"]:
        lines.append(
            f"| {step['step']} | {step['fit_selected']} | {step['promoted']} | {step['selected_after_step']} |"
        )
    lines += [
        "",
        "## All development variants",
        "",
        "| Configuration | Split | Correct | Incorrect | Unknown | Precision among judged | Coverage | Usable genuine pairs |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for variant in development["variants"]:
        for split in ("fit", "validate"):
            r = variant[split]["overall"]
            lines.append(
                f"| {variant['id']} | {split} | {r['supported']} | {r['contradicted']} | {r['untestable']} | {pct(r['precision'])} | {pct(r['coverage'])} | {r['usable_positive_pairs']}/{r['positive_pairs']} |"
            )
    for split in ("fit", "validate"):
        r = development["orb"][split]["overall"]
        lines.append(
            f"| ORB same pairs | {split} | {r['supported']} | {r['contradicted']} | {r['untestable']} | {pct(r['precision'])} | {pct(r['coverage'])} | {r['usable_positive_pairs']}/{r['positive_pairs']} |"
        )
    lines += ["", "## Configuration identities", ""]
    for variant in development["variants"]:
        lines += [f"- `{variant['id']}`: `{variant['variant']}`"]
    lines += ["", f"Selected: `{development['selected']}`", ""]
    test = result.get("test")
    if test:
        lines += [
            "## Fresh OldTownFall end-to-end test",
            "",
            "| Detector | Correct | Incorrect | Unknown | Precision among judged | Coverage | Raw event hits | Events with usable correspondences |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for method, value in test["aggregate"].items():
            r = value["features"]["overall"]
            lines.append(
                f"| {method} | {r['supported']} | {r['contradicted']} | {r['untestable']} | {pct(r['precision'])} | {pct(r['coverage'])} | {value['raw_event_hits']}/{value['events']} | {value['usable_event_hits']}/{value['events']} |"
            )
        lines += [
            "",
            "### Raw candidate retrieval",
            "",
            "| Detector | Correct pairs | False pairs | Unknown pairs |",
            "| --- | ---: | ---: | ---: |",
        ]
        for method, r in test["aggregate"].items():
            lines.append(
                f"| {method} | {r['candidate_true']} | {r['candidate_false']} | {r['candidate_unknown']} |"
            )
    else:
        lines += [
            "## Fresh test",
            "",
            "Not run yet. No test-data promotion decisions are permitted.",
        ]
    lines += [
        "",
        "## Limits and provenance",
        "",
        "- Usable means >=20 independently correct correspondences on a reference-positive pair. This is an evaluator diagnostic, not a runtime ground-truth filter or an accepted SLAM loop.",
        "- Promotions require cumulative baseline retention per scene and overall: >=90% correct matches, >=95% usable genuine pairs, nondecreasing judged precision, and fewer bad matches on fit and validation.",
        "- Threshold filtering and feature changes can discard correct matches; all failed promotions are retained in the report. Unknowns are never counted as incorrect.",
        "- Pair labels retain the original overlap policy; depth-v2 judges features separately. Incomplete reference labels withhold overall recall claims.",
        "- Shared scenes across development splits and one new synthetic test environment do not establish real-world or universal superiority. Upstream pretraining exposure is unaudited.",
        "- No fine-tuning, RANSAC selection, downstream SLAM trajectory test or latency promotion is performed.",
        "",
        f"Artifact root: `{result['artifact_root']}`",
        "",
        f"Pair-list SHA256: `{development['fixed_pairs_sha256']}`",
        "",
        f"Experiment freeze SHA256: `{development['experiment_freeze_sha256']}`",
        "",
        f"Selected configuration SHA256: `{development['selected_configuration_sha256']}`",
        "",
    ]
    return "\n".join(lines)
