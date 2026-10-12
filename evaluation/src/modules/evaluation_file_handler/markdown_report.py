"""Human-readable view of the same measurements saved in the JSON report."""


def _cell(value) -> str:
    if value is None:
        return "Not evaluated"
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("|", "\\|")
        .replace("\r", " ")
        .replace("\n", " ")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def render_report(report: dict, json_name: str, artifact_name: str) -> str:
    if "comparison_result" in report:
        if "descriptor_analysis" in report["comparison_result"]:
            from tasks.descriptor_analysis.report import render

            return render(report["comparison_result"]["descriptor_analysis"])
        if "matching_diagnostics" in report["comparison_result"]:
            from tasks.matching_diagnostics.report import render

            return render(report["comparison_result"]["matching_diagnostics"])
        if "matching_optimization" in report["comparison_result"]:
            from tasks.matching_optimization.report import render

            return render(report["comparison_result"]["matching_optimization"])
        if "reference_depth_v2" in report["comparison_result"]:
            from tasks.reference_depth_v2.report import render

            return render(report["comparison_result"]["reference_depth_v2"])
        if "unseen_tartanair" in report["comparison_result"]:
            from tasks.unseen_tartanair.report import render

            return render(report["comparison_result"]["unseen_tartanair"])
        if "optimization" in report["comparison_result"]:
            from tasks.optimization.report import render

            return render(report["comparison_result"]["optimization"])
        from tasks.loop_closure.comparison.comparison import render_comparison

        return render_comparison(report["comparison_result"])
    retrieval_cases = [
        case for case in report["cases"] if case.get("benchmark_type") == "image_retrieval"
    ]
    if retrieval_cases:
        retrieval_report = _render_retrieval(
            {**report, "cases": retrieval_cases}, json_name, artifact_name
        )
        slam_cases = [
            case for case in report["cases"] if case.get("benchmark_type") != "image_retrieval"
        ]
        if slam_cases:
            return (
                retrieval_report
                + "\n"
                + render_report({**report, "cases": slam_cases}, json_name, artifact_name)
            )
        return retrieval_report
    lines = ["# LDO evaluation report", "", f"**Status:** {_cell(report['status'])}", ""]
    for label, key in [
        ("Run ID", "run_id"),
        ("Started", "started_at"),
        ("Ended", "ended_at"),
        ("Timezone", "timezone"),
        ("Seed", "seed"),
    ]:
        if key in report:
            lines.extend([f"**{label}:** {_cell(report[key])}", ""])
    if report.get("error"):
        lines.extend([f"**Run error:** {_cell(report['error'])}", ""])
    config = report.get("config", {})
    if config.get("dataset", {}).get("root"):
        lines.extend([f"**Dataset root:** {_cell(config['dataset']['root'])}", ""])
    if "seed" in config.get("run", {}):
        lines.extend([f"**Configured seed:** {_cell(config['run']['seed'])}", ""])
    lines.extend(
        [
            "## Loop detection results",
            "",
            "Counts describe reported events and attempts. Repeated attempts can refer to the same physical revisit.",
            "",
            "| Benchmark | Status | Queries | Eligible queries | Proposals | Geometry accepted | Geometry rejected | Final decisions | Loops accepted | Constraints inserted |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    count_keys = [
        "loop_query_count",
        "eligible_loop_query_count",
        "proposal_count",
        "geometric_acceptance_count",
        "geometric_rejection_count",
        "loop_decision_count",
        "detected_loop_count",
        "constraint_count",
    ]
    for case in report["cases"]:
        values = [case["benchmark_id"], case["status"], *(case[key] for key in count_keys)]
        lines.append("| " + " | ".join(_cell(value) for value in values) + " |")
    lines.extend(
        [
            "",
            "Geometric acceptance is an intermediate result. Loops accepted counts final native decisions; constraints inserted counts actual map edges. Map merges are separate events.",
            "",
            "## Detection accuracy",
            "",
            "| Benchmark | True positives | False positives | Missed loops | Precision | Recall |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for case in report["cases"]:
        metrics = case["detection_metrics"]
        values = [
            case["benchmark_id"],
            *(metrics[key] for key in ("tp", "fp", "fn", "precision", "recall")),
        ]
        lines.append("| " + " | ".join(_cell(value) for value in values) + " |")
    lines.extend(
        [
            "",
            "A geometric rejection is not a false-positive label. Independent loop ground truth is required to measure accuracy.",
            "",
            "## Benchmark details",
            "",
        ]
    )
    for case in report["cases"]:
        lines.extend(
            [
                f"### {_cell(case['benchmark_id'])}",
                "",
                f"- Status: {_cell(case['status'])}",
                f"- Events recorded: {case['event_count']}",
            ]
        )
        for label, key in [
            ("Exit code", "exit_code"),
            ("Execution duration (seconds)", "execution_seconds"),
        ]:
            if key in case:
                lines.append(f"- {label}: {_cell(case[key])}")
        reason = case["detection_metrics"].get("availability_reason")
        if reason:
            lines.append(f"- Accuracy availability: {_cell(reason)}")
        for error in case.get("errors", []):
            lines.append(f"- Error: {_cell(error)}")
        lines.extend(["", "| Event | Count |", "| --- | ---: |"])
        for name, count in sorted(case["event_counts"].items()):
            lines.append(f"| {_cell(name)} | {count} |")
        lines.append("")
        if case.get("rejection_reasons"):
            lines.extend(
                ["#### Rejection reasons", "", "| Failed gate | Attempts |", "| --- | ---: |"]
            )
            for reason, count in sorted(case["rejection_reasons"].items()):
                lines.append(f"| {_cell(reason)} | {count} |")
            lines.append("")
        if case.get("verification_gates"):
            lines.extend(
                [
                    "#### Geometric verification gates",
                    "",
                    "Only reached gates are counted. Observed values must be at least the threshold. RANSAC convergence uses 0 for failure and 1 for success.",
                    "",
                    "| Gate | Reached | Passed | Failed | Observed min | Observed max | Threshold |",
                    "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
                ]
            )
            for gate, summary in sorted(case["verification_gates"].items()):
                values = [
                    gate,
                    *(
                        summary[key]
                        for key in (
                            "reached",
                            "passed",
                            "failed",
                            "minimum",
                            "maximum",
                            "threshold",
                        )
                    ),
                ]
                lines.append("| " + " | ".join(_cell(value) for value in values) + " |")
            lines.append("")
        if case.get("solver_diagnostics"):
            lines.extend(
                [
                    "#### RANSAC internal measurements",
                    "",
                    "| Measurement | Attempts measured | Minimum | Maximum | Mean |",
                    "| --- | ---: | ---: | ---: | ---: |",
                ]
            )
            for name, summary in sorted(case["solver_diagnostics"].items()):
                mean = summary["total"] / summary["count"]
                lines.append(
                    f"| {_cell(name)} | {summary['count']} | {summary['minimum']} | {summary['maximum']} | {mean:.2f} |"
                )
            lines.append("")
        if case.get("retrieval_count"):
            lines.extend(
                [
                    "#### Candidate retrieval and local-map exclusions",
                    "",
                    f"Retrieval calls: {case['retrieval_count']}; calls returning no loop candidates: {case['empty_loop_retrieval_count']}.",
                    "",
                    "Connected candidates are already represented by local map links; skipping them is a native policy, not a geometric rejection. A pair can appear at several stages. Counts below include same-map candidates only.",
                    "",
                    "| Selection stage | Outcome | Pair records |",
                    "| --- | --- | ---: |",
                ]
            )
            for stage, reasons in sorted(case["candidate_selection"].items()):
                for reason, count in sorted(reasons.items()):
                    lines.append(f"| {_cell(stage)} | {_cell(reason)} | {count} |")
            lines.append("")
            if case.get("candidate_census"):
                census = case["candidate_census"]
                lines.extend(
                    [
                        f"Candidate census consistent: **{_cell(census['consistent'])}**. Recorded selected candidates match native returned vectors; geometry-filter passes match BoW geometric attempts.",
                        "",
                    ]
                )
        if case.get("revisit_validation"):
            validation = case["revisit_validation"]
            lines.extend(
                [
                    "#### Historical viewpoint validation",
                    "",
                    f"Status: {_cell(validation['status'])}.",
                    "",
                ]
            )
            for label, key in [
                ("Reason", "reason"),
                ("Query timestamp (ns)", "query_timestamp_ns"),
                ("Historical timestamp (ns)", "historical_timestamp_ns"),
                ("Query keyframe ID", "query_keyframe_id"),
                ("Historical keyframe ID", "historical_keyframe_id"),
                ("Time separation (seconds)", "time_separation_seconds"),
                ("Ground-truth position distance (m)", "position_distance_m"),
                ("Ground-truth orientation difference (degrees)", "orientation_difference_degrees"),
                ("Independent image matches", "feature_matches"),
                ("Fundamental matrix inliers", "fundamental_inliers"),
                ("Homography inliers", "homography_inliers"),
                ("Inlier image coverage", "inlier_image_coverage"),
            ]:
                if key in validation:
                    lines.append(f"- {label}: {_cell(validation[key])}")
            lines.extend(
                [
                    "",
                    "This validates visual-overlap evidence for one pair; it is not a precision/recall label or native 3D verification.",
                    "",
                ]
            )
            for outcome in validation.get("selection_history", []):
                lines.append(
                    f"- Native selection: {_cell(outcome['stage'])} → {_cell(outcome['reason'])}"
                )
            lines.append("")
            for prefix in ("query", "historical"):
                if f"{prefix}_image" in validation:
                    lines.extend(
                        [
                            f"**{prefix.capitalize()} camera image**",
                            "",
                            f"![{prefix.capitalize()} camera image]({validation[f'{prefix}_image']})",
                            "",
                        ]
                    )
            if validation.get("method"):
                lines.extend([_cell(validation["method"]), ""])
            if validation.get("proximity_selection_counts"):
                lines.extend(
                    [
                        "**Selection of nearby historical viewpoints**",
                        "",
                        "These counts use position below 1 m, orientation below 30 degrees, and time separation above 20 s. They are proximity diagnostics, not independently verified visual loops.",
                        "",
                        "| Stage | Outcome | Pair records |",
                        "| --- | --- | ---: |",
                    ]
                )
                for stage, reasons in sorted(validation["proximity_selection_counts"].items()):
                    for reason, count in sorted(reasons.items()):
                        lines.append(f"| {_cell(stage)} | {_cell(reason)} | {count} |")
                lines.append("")
    lines.extend(
        [
            "## Raw results",
            "",
            f"- [Machine-readable report]({json_name})",
            f"- [All recorded events]({artifact_name}/events.jsonl)",
            "",
        ]
    )
    if report["status"] != "complete":
        lines.extend(
            [
                "This report is partial. Counts reflect only events received so far; they do not establish completed benchmark performance.",
                "",
            ]
        )
    return "\n".join(lines)


def _render_retrieval(report, json_name, artifact_name):
    lines = ["# LDO image retrieval evaluation", "", f"**Status:** {_cell(report['status'])}", ""]
    for label, key in [
        ("Run ID", "run_id"),
        ("Started", "started_at"),
        ("Ended", "ended_at"),
        ("Seed", "seed"),
    ]:
        if key in report:
            lines.extend([f"**{label}:** {_cell(report[key])}", ""])
    if report.get("mode") == "frozen_detector_trace_replay":
        lines.extend(
            [
                "**Replay scope:** Retrieval and feature assignments are frozen from the recorded source run. Detector timing tables are the source measurements. This run repeats only stereo preparation and offline feature evaluation.",
                "",
            ]
        )
    if "seed" in report.get("config", {}).get("run", {}):
        lines.extend([f"**Configured seed:** {_cell(report['config']['run']['seed'])}", ""])
    if report.get("error"):
        lines.extend([f"**Run error:** {_cell(report['error'])}", ""])
    lines.extend(
        [
            "This evaluates configured standalone visual retrieval and matching detectors. It does not run tracking, local mapping, covisibility filtering, geometric loop verification, or loop correction.",
            "",
            "## Retrieval results",
            "",
            "Candidates are historical image suggestions, not accepted loop closures. Multiple suggestions can describe the same place.",
            "",
            "| Benchmark | Status | Queries | Eligible queries | Candidate records | Empty eligible queries | Featureless queries |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for case in report["cases"]:
        summary = case.get("image_retrieval", {})
        values = [
            case["benchmark_id"],
            case["status"],
            *(
                summary.get(key, 0)
                for key in (
                    "queries",
                    "eligible_queries",
                    "candidate_count",
                    "empty_eligible_queries",
                    "featureless_queries",
                )
            ),
        ]
        lines.append("| " + " | ".join(_cell(value) for value in values) + " |")
    lines.extend(
        [
            "",
            "## Accuracy",
            "",
            "True positives, false positives, missed revisits, precision, and recall: **not evaluated**. Independent visual-overlap labels and a fixed evaluation protocol are required. Similarity scores are not probabilities.",
            "",
        ]
    )
    for case in report["cases"]:
        policy = case["retrieval_policy"]
        lines.extend(
            [
                f"## {_cell(case['benchmark_id'])}",
                "",
                f"- Camera: {_cell(policy['camera'])}; sampling: {_cell(policy['sample_hz'])} Hz",
                f"- Temporal exclusion: {_cell(policy['temporal_exclusion_seconds'])} seconds; top K: {_cell(policy['top_k'])}",
                "- Query happens before insertion. No future or temporally excluded images are eligible.",
                f"- Ranking: {_cell(policy['ranking'])}",
                f"- IMU use: {_cell(policy['imu_usage'])}",
                f"- Detector: {_cell(policy.get('detector_id', 'ORB + DBoW2'))}",
                f"- Pinned source revision: {_cell(policy['provenance']['revision'])}",
                f"- Replay SHA-256: {_cell(policy['replay_sha256'])}",
            ]
        )
        if policy.get("upstream_parity_check"):
            parity = policy["upstream_parity_check"]
            lines.append(
                f"- Upstream reference check passed: {_cell(parity['passed'])}; exact pixels, descriptors, BoW and pair score on two real images"
            )
        if policy.get("model_manifest"):
            manifest = policy["model_manifest"]
            lines.append(
                f"- Model manifest: {_cell(manifest['manifest_id'])}; device: {_cell(manifest['device'])}; GPU: {_cell(manifest.get('gpu'))}"
            )
        duration_label = (
            "Offline checker seconds"
            if report.get("mode") == "frozen_detector_trace_replay"
            else "Execution seconds (including setup)"
        )
        for label, key in [
            ("Exit code", "exit_code"),
            (duration_label, "execution_seconds"),
        ]:
            if key in case:
                lines.append(f"- {label}: {_cell(case[key])}")
        for error in case.get("errors", []):
            lines.append(f"- Error: {_cell(error)}")
        lines.extend(
            [
                "",
                "### Per-image timings",
                "",
                "Timings exclude model/vocabulary initialization and offline XYZ evaluation. Exact retrieval cost grows with eligible history. Matching timings include cache misses and all candidate pairs for the query.",
                "",
                "| Stage | Mean (ms) | Min (ms) | Max (ms) |",
                "| --- | ---: | ---: | ---: |",
            ]
        )
        for name, timing in case["image_retrieval"]["timings_ms"].items():
            lines.append(
                f"| {_cell(name)} | {timing['total'] / timing['count']:.3f} | {timing['minimum']:.3f} | {timing['maximum']:.3f} |"
            )
        runtime = case.get("runtime")
        if runtime:
            latency = runtime.get("query_latency_ms", {})
            lines.extend(
                [
                    "",
                    "### Detector resources",
                    "",
                    f"- Detector run including artifact publication: {runtime['inference_seconds']:.3f} seconds; offline XYZ evaluation excluded.",
                    f"- Query latency p50 / p95: {_cell(latency.get('p50'))} / {_cell(latency.get('p95'))} ms (includes initialization warm-up).",
                    f"- Peak PyTorch GPU allocation: {runtime['peak_gpu_bytes'] / 1024**3:.3f} GiB; driver and other-process allocations excluded.",
                    f"- CPU feature cache at completion: {runtime['cached_feature_bytes'] / 1024**2:.2f} MiB; descriptor index allocation: {runtime['descriptor_index_bytes'] / 1024**2:.2f} MiB.",
                    f"- Feature cache hits / misses: {runtime['cache_hits']} / {runtime['cache_misses']}.",
                    "",
                ]
            )
        review = case.get("candidate_evaluation")
        if review:
            lines.extend(_candidate_review(review))
        diagnostic = case.get("retrieval_diagnostic")
        if diagnostic:
            lines.extend(
                [
                    "",
                    "### Previously inspected revisit",
                    "",
                    diagnostic["description"],
                    "",
                    f"Query timestamp: {diagnostic['query_timestamp_ns']} ns. Historical target timestamp: {diagnostic['historical_timestamp_ns']} ns.",
                    "",
                    f"Historical target rank: {_cell(diagnostic['target_rank']) if diagnostic['target_rank'] is not None else 'Not returned in top K'}. This is a qualitative check of one pair, not an accuracy measurement.",
                    "",
                    "| Rank | Historical timestamp (ns) | DBoW2 score |",
                    "| ---: | ---: | ---: |",
                ]
            )
            for candidate in diagnostic["candidates"]:
                lines.append(
                    f"| {candidate['rank']} | {candidate['historical_timestamp_ns']} | {candidate['score']:.6f} |"
                )
        lines.extend(["", "### Events", "", "| Event | Count |", "| --- | ---: |"])
        for name, count in sorted(case["event_counts"].items()):
            lines.append(f"| {_cell(name)} | {count} |")
        lines.append("")
    lines.extend(
        [
            "## Raw results",
            "",
            f"- [Machine-readable report]({json_name})",
            f"- [All queries and ranked candidates]({artifact_name}/events.jsonl)",
            "",
        ]
    )
    if report["status"] != "complete":
        lines.extend(["This report is partial; counts reflect events received so far.", ""])
    return "\n".join(lines)


def _candidate_review(review):
    policy = review["provenance"]["policy"]
    if policy.get("version", 0) >= 8 and policy.get("stereo_enabled"):
        return _feature_review(review)
    stereo_enabled = policy.get("stereo_enabled", False)
    lines = [
        "",
        "### Independent candidate evidence",
        "",
        f"Checker status: **{_cell(review['status'])}**; pairs reviewed: **{review['checked_pairs']}**.",
        "",
        f"Ground-truth admission: **{review.get('excluded_pairs', 0)} pairs excluded** before evaluation because a reference pose was unavailable. Evaluated plus excluded pairs must equal all returned candidates. Exclusions are not XYZ failures or accuracy labels.",
        "",
        (
            "Existing temporal ORB feature matches are assigned stereo depth by the configured stereo backend. Their XYZ positions are transformed into the reference world frame and compared, with bidirectional reprojection checks. 2D geometry remains supporting diagnostics."
            if stereo_enabled
            else "ORB mutual Hamming matches are tested against EuRoC reference camera geometry and an independently estimated homography."
        )
        + " The checker uses exported ORB correspondences and reference geometry; DBoW2 scores do not determine the outcome.",
        "",
        "**Suspicious means possible false positive requiring review. Overlap supported means supporting evidence. Inconclusive means evidence is insufficient. None is a confirmed TP/FP label.**",
        "",
        "| Outcome | Candidate pairs |",
        "| --- | ---: |",
    ]
    for outcome in ("overlap_supported", "suspicious", "inconclusive"):
        lines.append(f"| {_cell(outcome)} | {review['outcome_counts'].get(outcome, 0)} |")
    lines.extend(
        [
            "",
            "| Candidate rank | Overlap supported | Suspicious | Inconclusive |",
            "| ---: | ---: | ---: | ---: |",
        ]
    )
    for rank, counts in sorted(review["rank_outcome_counts"].items(), key=lambda row: int(row[0])):
        lines.append(
            f"| {rank} | {counts.get('overlap_supported', 0)} | {counts.get('suspicious', 0)} | {counts.get('inconclusive', 0)} |"
        )
    lines.extend(["", "| Reason | Pairs |", "| --- | ---: |"])
    for reason, count in sorted(review["reason_counts"].items()):
        lines.append(f"| {_cell(reason)} | {count} |")
    if "ransac_totals" in review and policy.get("version", 0) < 8:
        r = review["ransac_totals"]
        lines.extend(
            [
                "",
                "#### Temporal RANSAC before XYZ",
                "",
                f"USAC_MAGSAC fits a fundamental matrix from undistorted image points, without ground truth. Gate: {policy['ransac_error_px']} px; confidence: {policy['ransac_confidence']}; maximum iterations: {policy['ransac_max_iterations']}.",
                "",
                f"Raw ORB matches: {r['raw_matches']}; retained for XYZ: {r['retained_matches']}; filtered out: {r['rejected_matches']}. Pair fit statuses: {r['status_counts']}.",
                "",
                "Pairs with fewer than eight matches skip fitting and keep their matches, explicitly marked unvalidated by RANSAC. Failed fits send zero matches to XYZ. XYZ support uses the retained set as its denominator; raw counts remain saved. Filtering is not a proof that a match is correct.",
                "",
            ]
        )
    if stereo_enabled:
        totals = review.get("stereo_totals", {})
        lines.extend(
            [
                f"Stereo correspondence backend: **{policy.get('stereo_backend', 'orb_mutual')}**. Model source, checkpoint and runtime are pinned in saved provenance. Left-right consistency is checked before triangulation.",
                "",
            ]
        )
        lines.extend(
            [
                "",
                "#### Stereo XYZ evidence",
                "",
                f"Pairs with enough reliable dual-depth matches for the saved support requirement: {totals.get('pairs_with_reliable_stereo', 0)}. Landmark comparison records: {totals.get('paired_landmarks', 0)}; consistent records: {totals.get('consistent_landmarks', 0)}. These are repeated observations, not unique environment landmarks.",
                "",
                f"Support requires at least ceil(reported ORB matches * {policy['minimum_inlier_ratio']}) consistent landmarks. Grid coverage is not a decision gate. Passing ratio uses all reported matches before depth filtering. XYZ consistency requires squared Mahalanobis error ≤ {policy['stereo_world_mahalanobis_squared_maximum']} and cross-view reprojection ≤ {policy['stereo_cross_reprojection_px']} px in both directions.",
                "",
                f"Suspicion requires enough reliable paired landmarks for the saved support requirement and depth-valid agreement ratio ≤ {policy['contradiction_maximum_inlier_ratio']}. Missing or unreliable depth remains inconclusive.",
                "",
                f"Uncertainty assumptions: pixel sigma {policy['stereo_pixel_sigma_px']} px, reference-position sigma {policy['reference_position_sigma_m']} m, reference-orientation sigma {policy['reference_orientation_sigma_degrees']}°. These are assumed noise values, not supplied ground-truth covariance. Calibration uncertainty and correlated pose errors are not modeled.",
                "",
                "Full per-landmark camera/world XYZ, errors and uncertainty are retained in the native run's candidate_checks/pairs.jsonl. The event stream retains each pair's evidence-file path and line number.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "",
                f"Diagnostic thresholds: at least {policy['minimum_matches']} mutual matches; {policy['minimum_inliers']} reference inliers; inlier ratio ≥ {policy['minimum_inlier_ratio']}; coverage ≥ {policy.get('minimum_image_coverage', 0)}; reference error ≤ {policy['ground_truth_error_px']} pixels.",
                "",
                f"Suspicion requires homography support and reference inlier ratio ≤ {policy['contradiction_maximum_inlier_ratio']}.",
                "",
            ]
        )
    lines.extend(
        [
            "Thresholds are provisional and have not been validated as a ground-truth labeling protocol.",
            "",
            "EuRoC ground-truth orientation/timing uncertainty can affect reference geometry. Position distance alone never labels a pair false. Only returned pairs are checked, so this check cannot measure missed loops or recall.",
            "",
        ]
    )
    if "evaluation_seconds" in review:
        lines.extend(
            [
                f"Offline checker duration: {review['evaluation_seconds']:.2f} seconds. This is excluded from the native retrieval stage timings.",
                "",
            ]
        )
    for example in review.get("examples", []):
        measurement, pose = example["measurements"], example["pose_evidence"]
        lines.extend(
            [
                f"#### {_cell(example['outcome'])}: rank {example['rank']}",
                "",
                f"Query: {example['query_timestamp_ns']} ns; history: {example['historical_timestamp_ns']} ns.",
                "",
                f"Mutual ORB matches: {measurement['match_count']}; reference inliers: {measurement['reference_inliers']}; ratio: {measurement['reference_inlier_ratio']:.3f}; homography inliers: {measurement['homography_inliers']}.",
                "",
            ]
        )
        if pose["available"]:
            lines.extend(
                [
                    f"Camera separation: {pose['camera_position_distance_m']:.3f} m; orientation difference: {pose['camera_orientation_difference_degrees']:.2f}°.",
                    "",
                ]
            )
        stereo = example.get("stereo")
        if stereo:
            lines.extend(
                [
                    f"Reliable paired stereo landmarks: {stereo.get('paired_landmarks', 0)}; XYZ/reprojection-consistent: {stereo.get('consistent_landmarks', 0)}. Median XYZ disagreement: {_cell(stereo.get('xyz_median_error_m'))} m; median cross reprojection: {_cell(stereo.get('cross_reprojection_median_px'))} px.",
                    "",
                ]
            )
        lines.extend([f"![Candidate pair evidence]({example['image']})", ""])
    return lines


def _feature_review(review):
    counts = review.get("feature_totals", {})
    supported, contradicted, untestable = (
        counts.get(v, 0) for v in ("supported", "contradicted", "untestable")
    )
    reported, testable = supported + contradicted + untestable, supported + contradicted

    def percentage(n, d):
        return f"{100 * n / d:.2f}%" if d else "Not evaluated"

    timings = review.get("feature_timings_ms", {})
    learned = review["provenance"].get("model_manifest")
    description = (
        f"{_cell(learned['variant'])} proposes image pairs and saved learned feature correspondences. "
        "The same pinned stereo and numerical XYZ policy used for the ORB baseline evaluates every reported correspondence."
        if learned
        else "DBoW2 proposes image pairs. Mutual Hamming matching of exported upstream ORB descriptors proposes feature correspondences."
    )
    lines = [
        "",
        "### Feature correspondence XYZ evaluation",
        "",
        f"Status: **{review['status']}**. Candidate image pairs evaluated: **{review['checked_pairs']}**; excluded for missing reference poses: **{review.get('excluded_pairs', 0)}**.",
        "",
        description
        + " Every correspondence is evaluated, without temporal RANSAC or grid coverage filtering.",
        "",
        "| Feature verdict | Correspondence observations |",
        "| --- | ---: |",
        f"| Supported | {supported} |",
        f"| Contradicted | {contradicted} |",
        f"| Untestable | {untestable} |",
        f"| Total reported | {reported} |",
        "",
        f"Testable: **{testable}**. Contradiction rate (contradicted / testable): **{percentage(contradicted, testable)}**. Evaluation coverage (testable / reported): **{percentage(testable, reported)}**.",
        "",
        "Supported means reliable stereo estimates agree in the reference world. Contradicted means reliable estimates disagree: evidence of a suspected false correspondence. Untestable means required reliable depth/pose/uncertainty is unavailable. These verdicts do not declare an entire loop candidate true or false.",
        "",
        f"XYZ threshold: squared Mahalanobis error <= {review['provenance']['policy']['stereo_world_mahalanobis_squared_maximum']}. Reprojection is a separate diagnostic and does not override the XYZ feature verdict.",
        "",
        f"Stereo preparation and reprojection time: {timings.get('stereo_preparation_and_reprojection', 0) / 1000:.3f} seconds. Numerical XYZ-check time: {timings.get('xyz_checks', 0) / 1000:.3f} seconds. Cached frame reuse is included; these are evaluator timings, not measured downstream computation wasted or saved.",
        "",
        "Counts describe correspondence observations, including repeated observations across image pairs; not unique environment landmarks. Full per-feature verdicts, failure reasons, positions, uncertainty and timings are saved in candidate_checks/pairs.jsonl.",
        "",
        "The numerical checker consumes two prepared observations, not image files. Reference-pose and stereo uncertainty assumptions remain provisional; this is independent geometric evidence, not ground-truth feature identity.",
        "",
    ]
    breakdown = review.get("coverage_breakdown", {})
    domain_counts = breakdown.get("domain_verdict_counts", {})
    if any(key.startswith("primary_overlap_") for key in domain_counts):
        lines.extend(
            [
                "#### Coverage by original stereo image domain",
                "",
                "ORB extracts on rectified images; learned features can cover the full raw image. Report both domains to avoid attributing differences in visible area to matcher quality. These domains do not equalize candidate pairs, feature budgets or depth distributions.",
                "",
                "| Domain | Reported | Testable | XYZ coverage |",
                "| --- | ---: | ---: | ---: |",
            ]
        )
        for domain in ("primary_overlap", "additional_field", "unknown"):
            values = [
                domain_counts.get(f"{domain}_{verdict}", 0)
                for verdict in ("supported", "contradicted", "untestable")
            ]
            if sum(values):
                lines.append(
                    f"| {_cell(domain)} | {sum(values)} | {sum(values[:2])} | {percentage(sum(values[:2]), sum(values))} |"
                )
        lines.append("")
    if breakdown.get("depth_failure_pair_counts"):
        lines.extend(
            [
                "#### Why matches remain untestable",
                "",
                "Each row is an exclusive query / history reason pair. The rows sum to all untestable observations. Reliable on one side is insufficient for the two-depth XYZ check.",
                "",
                "| Query / history depth reason | Observations | Share of untestable |",
                "| --- | ---: | ---: |",
            ]
        )
        for reason, count in sorted(
            breakdown["depth_failure_pair_counts"].items(), key=lambda item: (-item[1], item[0])
        ):
            lines.append(f"| {_cell(reason)} | {count} | {percentage(count, untestable)} |")
        lines.extend(
            [
                "",
                "Low parallax and uncertain depth indicate inadequate depth precision under the saved noise assumptions. They are abstentions, not incorrect matches. Expanded-field stereo recovery preserves primary observations and validates recovered ones using the same reliability gates; padding is never evidence.",
                "",
            ]
        )
    for example in review.get("examples", []):
        lines.extend(
            [
                f"#### Candidate rank {example['rank']}: feature counts",
                "",
                f"Query {example['query_timestamp_ns']}; history {example['historical_timestamp_ns']}. Counts: {example.get('stereo', {}).get('feature_counts', {})}.",
                "",
            ]
        )
    return lines
