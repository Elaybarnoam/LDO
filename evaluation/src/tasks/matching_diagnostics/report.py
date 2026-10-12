"""Human-readable failure mechanisms with explicit reference-only oracle limits."""


def render(result: dict) -> str:
    lines = [
        "# LDO matching failure diagnosis",
        "",
        f"Baseline events with >=20 correct matches: **{result['baseline_event_hits']}/{result['reference_events']}**.",
        "",
        "All original model outputs and XYZ verdicts are preserved. OldTownFall is used for post-test explanation only. Oracle associations are never model inputs.",
        "",
        "## Four weak events",
        "",
        "| Trajectory | Event start (s) | Retrieved positive pairs | Best reported correct | Maximum capacity of existing features | Finding |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for event in result["events"]:
        finding = (
            "Supported associations remain unused"
            if event["maximum_existing_feature_capacity"] >= 20
            else "Existing feature capacity is insufficient"
        )
        lines.append(
            f"| {event['trajectory']} | {event['start_ns'] / 1e9:.2f} | {len(event['pairs'])} | {event['best_reported_correct']} | {event['maximum_existing_feature_capacity']} | {finding} |"
        )
    totals = result["test_summary"]
    lines += [
        "",
        "Maximum capacity is the largest one-to-one assignment between the existing keypoints that passes the unchanged XYZ/reprojection evaluator. Best reported and maximum capacity are each maxima over the event's retrieved positive pairs; they can occur on different pairs.",
        "",
        "It is an evaluator upper bound, not evidence that a visual matcher can uniquely recover every edge or that a SLAM backend can accept the loop.",
        "",
        f"Across these {totals['pairs']} pairs: {totals['reported'].get('supported', 0)} reported supports, {totals['reported'].get('contradicted', 0)} contradictions and {totals['reported'].get('untestable', 0)} unknowns. Of the contradictions, {totals['near_gate_contradictions']} lie within twice both numerical gates; {totals['large_residual_contradictions']} have larger residuals. The near-gate diagnostic never relabels a failed match.",
        "",
        "## Independent development check",
        "",
        "Only the pre-existing fixed reference-positive development pairs are analyzed. These are separate factory/desert trajectories, not the four OldTownFall examples. Zero-match pairs remain included.",
        "",
        "| Split / scene | Positive pairs | Currently usable | Existing-feature oracle usable | Assignment-gap pairs | Capacity-limited pairs |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for split, values in result["development"].items():
        for scope, row in [("overall", values["overall"]), *values["scenes"].items()]:
            lines.append(
                f"| {split} / {scope} | {row['pairs']} | {row['usable_pairs']} | {row['oracle_usable_pairs']} | {row['assignment_gap_pairs']} | {row['capacity_limited_pairs']} |"
            )
    lines += ["", "## Detailed pair evidence", ""]
    for event in result["events"]:
        lines += [
            f"### {event['trajectory']} / {event['event_id']}",
            "",
            "| Query / history (s) | Correct / incorrect / unknown | Oracle capacity | Valid-depth query / history features | Query features projecting inside history | Unmatched features with supported alternatives | Median rejected pixel error |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for r in event["pairs"]:
            c = r["reported"]
            median = r["contradicted_pixel_error_px"]["median"]
            median_text = "N/A" if median is None else f"{median:.2f} px"
            lines.append(
                f"| {r['q'] / 1e9:.2f} / {r['h'] / 1e9:.2f} | {c['supported']} / {c['contradicted']} / {c['untestable']} | {r['maximum_supported_one_to_one_matches']} | {r['valid_query_depth_features']} / {r['valid_historical_depth_features']} | {r['query_features_projecting_inside_history']} | {r['unmatched_query_features_with_supported_alternatives']} | {median_text} |"
            )
    lines += [
        "",
        "## Interpretation and next experiment",
        "",
        "Prioritize association quality and low-overlap handling. Most failed matches in these events have large residuals, and three events have enough existing geometrically supported feature alternatives. Missing reference evidence and small localization errors do not explain most of these observed contradictions.",
        "",
        "The capacity-limited event also needs better observations, extraction or candidate selection. Its low capacity is conditional on the fixed keypoints, visibility and evaluator; it does not prove a specific detector defect.",
        "",
        "A stronger image-pair transformer is the next candidate experiment. Choose its settings on development data, require fewer incorrect matches and preservation of every baseline usable event ID on full fit/validation replays, then freeze and test on a new environment. No alternative model is adopted by this diagnostic task.",
        "",
        "## Reproduction and limits",
        "",
        "Run `python -m tasks.matching_diagnostics run` in the installed WSL environment with `PYTHONPATH=.:evaluation/src`. `check` returns exit code 2 while the saved baseline remains below the all-events diagnostic target; this is expected, not a tool failure.",
        "",
        "Reference projection alone checks field of view, not occlusion. Oracle edges additionally pass the complete frozen bidirectional depth/XYZ/reprojection test. Counts describe repeated image correspondences, not distinct world landmarks. No pose fitting, RANSAC, model training, reference-guided inference or tolerance relaxation is performed.",
        "",
        f"Artifacts: `{result['artifact_root']}`",
        "",
        f"Original test SHA256: `{result['source_test_results_sha256']}`",
        "",
        f"Analysis freeze identity: `{result['freeze_sha256']}`",
        "",
    ]
    return "\n".join(lines)
