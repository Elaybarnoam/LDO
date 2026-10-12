"""Read-only analysis of frozen traces and external XYZ evidence."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np

from .metrics import paired_interval, read_trace, retrieval_metrics
from .reference import load_reference, sha256, verify_images


def feature_profile(checks: Path) -> dict:
    summary = json.loads((checks / "summary.json").read_text(encoding="utf-8"))
    if summary.get("complete") is not True:
        raise ValueError("Comparison requires complete XYZ evidence")
    provenance = json.loads((checks / "provenance.json").read_text(encoding="utf-8"))
    pairs, totals = {}, Counter()
    digest = hashlib.sha256()
    with (checks / "pairs.jsonl").open("rb") as stream:
        for line in stream:
            digest.update(line)
            pair = json.loads(line)
            key = (pair["query_timestamp_ns"], pair["historical_timestamp_ns"])
            if key in pairs:
                raise ValueError("Duplicate XYZ evidence pair")
            counts = Counter(f["verdict"] for f in pair["stereo"]["feature_results"])
            if set(counts) - {"supported", "contradicted", "untestable"}:
                raise ValueError("Unknown XYZ verdict")
            counts = {v: counts[v] for v in ("supported", "contradicted", "untestable")}
            pairs[key] = {
                "counts": counts,
                "images": [
                    pair["measurements"][f"{side}_image_sha256"] for side in ("query", "historical")
                ],
            }
            totals.update(counts)
    if dict(totals) != summary["feature_totals"] or len(pairs) != summary["checked_pairs"]:
        raise ValueError("XYZ evidence does not reconcile with summary")
    return {
        "pairs": pairs,
        "policy": provenance["policy"],
        "source_hash": digest.hexdigest(),
        "provenance": provenance,
        "summary": summary,
    }


def summarize_features(pairs: dict) -> dict:
    totals = Counter()
    coverage, contradiction, support = [], [], []
    zero_matches = 0
    for item in pairs.values():
        counts = item["counts"]
        totals.update(counts)
        reported = sum(counts.values())
        judged = counts["supported"] + counts["contradicted"]
        support.append(counts["supported"])
        if reported:
            coverage.append(judged / reported)
        else:
            zero_matches += 1
        if judged:
            contradiction.append(counts["contradicted"] / judged)
    reported = sum(totals.values())
    judged = totals["supported"] + totals["contradicted"]
    return {
        "pairs": len(pairs),
        "zero_match_pairs": zero_matches,
        "feature_totals": {v: totals[v] for v in ("supported", "contradicted", "untestable")},
        "micro_coverage": judged / reported if reported else None,
        "micro_contradiction": totals["contradicted"] / judged if judged else None,
        "mean_supported_per_pair_including_zero": float(np.mean(support)) if support else None,
        "macro_coverage_nonempty_pairs": float(np.mean(coverage)) if coverage else None,
        "macro_contradiction_judgeable_pairs": float(np.mean(contradiction))
        if contradiction
        else None,
        "pairs_with_judgeable_features": len(contradiction),
    }


def compare(reference_root: Path, methods: dict, protocol: dict, fixed: bool = False) -> dict:
    manifest, reference = load_reference(reference_root)
    for filename, expected in manifest["reference_files"].items():
        if sha256(Path(filename)) != expected:
            raise ValueError("Reference pose or calibration file changed")
    if manifest["protocol"] != protocol:
        raise ValueError("Reference and comparison protocols differ")
    queries = [q["timestamp_ns"] for q in manifest["queries"]]
    stamps = list(map(int, manifest["images"]))
    traces, profiles = {}, {}
    source = {
        "reference_manifest": sha256(reference_root / "manifest.json"),
        "reference_pairs": sha256(reference_root / "pairs.jsonl"),
    }
    journal = reference_root / "reviews.jsonl"
    source["reviews"] = sha256(journal) if journal.exists() else None
    for name, paths in methods.items():
        verify_images(manifest, Path(paths["replay"]))
        traces[name] = read_trace(
            Path(paths["trace"]), stamps, protocol["exclusion_ns"], max(protocol["k_values"])
        )
        source[f"{name}_trace"] = sha256(Path(paths["trace"]))
        if paths.get("checks"):
            profiles[name] = feature_profile(Path(paths["checks"]))
            for (q, h), pair in profiles[name]["pairs"].items():
                if q not in stamps or h not in stamps or q - h < protocol["exclusion_ns"]:
                    raise ValueError("XYZ evidence contains an ineligible pair")
                if pair["images"] != [manifest["images"][str(s)]["sha256"] for s in (q, h)]:
                    raise ValueError("XYZ evidence image contents differ from reference")
                if not fixed and not any(
                    c["historical_timestamp_ns"] == h for c in traces[name][q]
                ):
                    raise ValueError("XYZ evidence is not from this detector trace")
            source[f"{name}_xyz"] = profiles[name]["source_hash"]
    result = {
        "sequence": manifest["sequence"],
        "reference_path": str(reference_root),
        "protocol": protocol,
        "source_sha256": source,
        "reference": {
            "pairs": len(reference),
            "labels": dict(Counter(p["label"] for p in reference.values())),
            "selected_queries": len(queries),
            "excluded_queries_missing_pose": len(manifest["excluded_queries_missing_pose"]),
        },
        "retrieval": {},
        "paired_uncertainty": {},
        "claim_validated": False,
        "claim_status": "No automatic superiority claim; independent labels and held-out evidence are required.",
    }
    for k in protocol["k_values"]:
        scores = {
            name: retrieval_metrics(reference, trace, queries, k) for name, trace in traces.items()
        }
        result["retrieval"][str(k)] = scores
        result["paired_uncertainty"][str(k)] = paired_interval(
            scores["orb"],
            scores["ldo"],
            protocol["seed"],
            protocol["bootstrap_block_queries"],
            protocol["bootstrap_samples"],
        )
        discoveries = Counter()
        for (q, h), item in reference.items():
            if item["label"] != "loop":
                continue
            found = [
                any(c["historical_timestamp_ns"] == h for c in traces[n][q][:k])
                for n in ("orb", "ldo")
            ]
            discoveries[
                {
                    (True, True): "both",
                    (False, True): "ldo_only",
                    (True, False): "orb_only",
                    (False, False): "neither",
                }[tuple(found)]
            ] += 1
        result["retrieval"][str(k)]["known_positive_discoveries"] = dict(discoveries)
    if len(profiles) == 2:
        if profiles["orb"]["policy"] != profiles["ldo"]["policy"]:
            raise ValueError("XYZ policies differ between methods")
        numerical_hashes = []
        for profile in profiles.values():
            hashes = profile["provenance"]["input_and_code_sha256"]
            numerical_hashes.append(
                {Path(p).name: value for p, value in hashes.items() if Path(p).name == "xyz.py"}
            )
        if not numerical_hashes[0] or numerical_hashes[0] != numerical_hashes[1]:
            raise ValueError("Numerical XYZ implementations differ or are unrecorded")
        left, right = (profiles[n]["pairs"] for n in ("orb", "ldo"))
        shared = set(left) & set(right)
        for key in shared:
            if left[key]["images"] != right[key]["images"]:
                raise ValueError("Matched image contents differ")
        if fixed and set(left) != set(right):
            raise ValueError("Controlled matching requires exactly identical pair sets")
        result["features"] = {
            "mode": "identical_fixed_pairs" if fixed else "different_detector_candidates",
            "shared_pairs": len(shared),
            "same_pair_sets": set(left) == set(right),
            "xyz_policy": profiles["orb"]["policy"],
            "all_pairs": {n: summarize_features(p["pairs"]) for n, p in profiles.items()},
            "shared_pair_diagnostic": {
                n: summarize_features({key: p["pairs"][key] for key in shared})
                for n, p in profiles.items()
            },
            "warning": "Pairs selected independently of detector outputs; this small sample does not establish superiority."
            if fixed
            else "Shared retrieved pairs are selection-biased; use independently chosen fixed pairs to isolate matching.",
        }
    return result


def render_comparison(result: dict) -> str:
    lines = [
        "# LDO versus ORB comparison",
        "",
        f"Sequence: **{result['sequence']}**",
        "",
        result["claim_status"],
        "",
        "XYZ remains external to both detectors. Unknown is not a false positive.",
        "",
    ]
    if result["retrieval"]:
        lines += [
            "## Retrieval",
            "",
            "| K | Method | True | False | Unknown | Precision bounds | Complete queries | Recall on complete queries | Query success |",
            "| --- | --- | ---: | ---: | ---: | --- | ---: | --- | --- |",
        ]

    def value(v):
        return "Unavailable" if v is None else f"{v:.4f}"

    for k, methods in result["retrieval"].items():
        for name in ("orb", "ldo"):
            m = methods[name]
            lines.append(
                f"| {k} | {name} | {m['true_positive']} | {m['false_positive']} | {m['unknown']} | "
                f"{value(m['precision_lower_bound'])}Ã¢â‚¬â€œ{value(m['precision_upper_bound'])} | "
                f"{m['complete_queries']}/{m['selected_queries']} | {value(m['complete_query_pair_recall'])} | {value(m['complete_query_success'])} |"
            )
    if result["retrieval"]:
        lines += [
            "",
            "Recall is withheld for incompletely labeled queries. Bounds include unknown returns. Missing-pose returns are separately excluded without rank refill.",
            "",
        ]
    features = result.get("features")
    if features:
        lines += [
            "## External XYZ evidence",
            "",
            f"Experiment: {features['mode']}; shared pairs: {features['shared_pairs']}.",
            "",
            "| Method | Pairs | Supported | Contradicted | Unknown | Coverage | Contradiction among judgeable | Mean supported/pair |",
            "| --- | ---: | ---: | ---: | ---: | --- | --- | --- |",
        ]
        for name, m in features["all_pairs"].items():
            t = m["feature_totals"]
            lines.append(
                f"| {name} | {m['pairs']} | {t['supported']} | {t['contradicted']} | {t['untestable']} | "
                f"{value(m['micro_coverage'])} | {value(m['micro_contradiction'])} | {value(m['mean_supported_per_pair_including_zero'])} |"
            )
        lines += ["", features["warning"], ""]
        lines += [
            "### Per-pair feature aggregates",
            "",
            "| Method | Zero-match pairs | Mean coverage of nonempty pairs | Mean contradiction of judgeable pairs |",
            "| --- | ---: | --- | --- |",
        ]
        for name, m in features["all_pairs"].items():
            lines.append(
                f"| {name} | {m['zero_match_pairs']} | {value(m['macro_coverage_nonempty_pairs'])} | {value(m['macro_contradiction_judgeable_pairs'])} |"
            )
        lines += [
            "",
            "Zero-match pairs remain in mean supported/pair; ratios without a denominator are unavailable.",
            "",
        ]
    if result.get("matching_experiment"):
        lines += [
            "## Matching controls",
            "",
            f"Budget mode: {result['matching_experiment']['budget_mode']}.",
            "",
            "An equal requested extraction cap does not guarantee equal detected feature counts. Original preprocessing is preserved.",
            "",
        ]
    verified = result.get("verified_connections")
    if verified:
        lines += [
            "## Shared operational loop verification",
            "",
            "Acceptance is a camera-observation decision, not proof of a correct loop. Independent labels assess accuracy.",
            "",
            "| Method | Pairs | Accepted | Rejected | Insufficient evidence | Correct accepted | Incorrect accepted | Unresolved accepted | Median translation error (m) | Median rotation error (degrees) |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
        ]
        for name, row in verified["methods"].items():
            lines.append(
                f"| {name} | {row['pairs']} | {row['accepted']} | {row['rejected']} | {row['insufficient_evidence']} | {row['correct_accepted']} | {row['incorrect_accepted']} | {row['unresolved_accepted']} | {value(row['median_translation_error_m'])} | {value(row['median_rotation_error_degrees'])} |"
            )
        lines += [
            "",
            f"Scope: query limit {verified['scope']['query_limit']}; fixed pairs {verified['scope']['fixed_pairs']}; independently selected queries only {verified['scope']['selected_reference_queries_only']}.",
            "",
            f"Pose-assessment threshold status: {verified['assessment_policy']['threshold_status']}.",
            "",
            "Pose-error medians above include all available estimates, including rejected ones; they are diagnostics, not accepted-loop accuracy.",
            "",
            "### Operational failure reasons",
            "",
        ]
        for name, row in verified["methods"].items():
            lines.append(
                f"- {name}: "
                + "; ".join(f"{reason}: {count}" for reason, count in row["reason_counts"].items())
            )
        lines += [
            "",
            "Verified-connection precision bounds, complete-query recall/success, miss reasons and paired uncertainty are in JSON. Missing reference labels withhold definitive accuracy.",
            "",
        ]
    audit = result.get("verification_xyz_audit")
    if audit:
        lines += [
            "## Verifier versus external XYZ audit",
            "",
            "Primary XYZ totals include every reported match, including rejected and insufficient-evidence candidates.",
            "",
            "| Method | Operational status | Pairs | Supported | Contradicted | Untestable | Strong XYZ support pairs |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
        ]
        for name, method in audit["methods"].items():
            for status, group in method["by_operational_status"].items():
                counts = group["feature_totals"]
                lines.append(
                    f"| {name} | {status} | {group['pairs']} | {counts['supported']} | {counts['contradicted']} | {counts['untestable']} | {method['strong_support_by_status'].get(status, 0)} |"
                )
        lines += [
            "",
            "Strong support is a descriptive highlight: at least 8 supported features, at least 80% support among judgeable features, and at least 40% evaluation coverage. It changes no verifier or XYZ gate.",
            "",
            "### Rejected candidates with strong XYZ support",
            "",
            "| Method | Query timestamp (ns) | History timestamp (ns) | Supported | Contradicted | Untestable | Inlier ratio | Pose translation error (m) | Rejection reason |",
            "| --- | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |",
        ]
        examples = sorted(
            (r for r in audit["rows"] if r["status"] == "rejected" and r["strong_xyz_support"]),
            key=lambda r: r["feature_counts"]["supported"],
            reverse=True,
        )
        for name in audit["methods"]:
            method_examples = [r for r in examples if r["method"] == name]
            accurate = sum(
                r["pose_assessment"].get("within_tolerance", False) for r in method_examples
            )
            lines.insert(
                lines.index("### Rejected candidates with strong XYZ support"),
                f"{name}: {len(method_examples)} rejected candidates meet the descriptive strong-support policy; estimated poses within the provisional reference tolerances: {accurate}. These are diagnostics, not independent loop labels.",
            )
            lines.insert(lines.index("### Rejected candidates with strong XYZ support"), "")
        display_examples = []
        for name in audit["methods"]:
            display_examples.extend([row for row in examples if row["method"] == name][:10])
        for row in display_examples:
            c = row["feature_counts"]
            lines.append(
                f"| {row['method']} | {row['query_timestamp_ns']} | {row['historical_timestamp_ns']} | {c['supported']} | {c['contradicted']} | {c['untestable']} | {value(row['verification_diagnostics'].get('inlier_ratio'))} | {value(row['pose_assessment'].get('translation_error_m'))} | {row['reason']} |"
            )
        lines += [
            "",
            "All pair-level results and diagnostics are in JSON. XYZ support of individual features does not itself establish a correct loop or a reliable estimated pose.",
            "",
        ]
    revisit = result.get("independent_revisits")
    if revisit:
        prep, frozen = revisit["preparation"], revisit["reference"]
        lines += [
            "## Independent revisit-event evaluation",
            "",
            f"Reference universe: {prep['reference_pairs']} pairs; {prep['pose_admitted_queries']} pose-admitted queries; {prep['queries_with_eligible_history']} with eligible history.",
            "",
            f"Pose-assisted proposals: {prep['pose_proposed_pairs']} pairs in {prep['proposal_intervals']} query intervals. Proposals are review aids, not ground-truth labels.",
            "",
            f"Independent interval reviews: {frozen['interval_reviews']}; frozen pair labels: {frozen['labels']}; confirmed continuous revisit events: {frozen['confirmed_events']}.",
            "",
            "| K | Method | Returned pairs | Correct | False | Unknown | Precision | Confirmed events detected | Overall event recall |",
            "| --- | --- | ---: | ---: | ---: | ---: | --- | --- | --- |",
        ]
        if not frozen["labels"].get("loop", 0) and not frozen["labels"].get("non_loop", 0):
            lines.insert(
                lines.index(
                    "| K | Method | Returned pairs | Correct | False | Unknown | Precision | Confirmed events detected | Overall event recall |"
                ),
                "No independent scene decisions have been supplied. Zero confirmed events means unreviewed reference, not absence of real loops.",
            )
            lines.insert(
                lines.index(
                    "| K | Method | Returned pairs | Correct | False | Unknown | Precision | Confirmed events detected | Overall event recall |"
                ),
                "",
            )
        for k, methods in revisit["metrics"].items():
            for name, m in methods.items():
                lines.append(
                    f"| {k} | {name} | {m['returned_pairs']} | {m['true_positive_pairs']} | {m['false_positive_pairs']} | {m['unknown_pairs']} | {value(m['precision'])} | {str(m['detected_confirmed_events']) + '/' + str(m['confirmed_events']) if m['confirmed_events'] else 'Unavailable'} | {value(m['event_recall'])} |"
                )
        lines += [
            "",
            "Unknown returns are not false positives. Overall event recall is withheld until the full reference is independently labeled. Repeated returned frames do not create additional revisit events.",
            "",
            f"Development matched-precision operating points available: {revisit['matched_precision'].get('available', revisit['matched_precision'].get('mode', False))}.",
            "",
        ]
        lines += [
            "### Pose-proposal diagnostics (not loop truth)",
            "",
            "| K | Method | Returns inside pose proposals | Proposal intervals reached |",
            "| --- | --- | ---: | --- |",
        ]
        for k, methods in revisit["pose_proposal_diagnostics"].items():
            for name, m in methods.items():
                lines.append(
                    f"| {k} | {name} | {m['returned_pairs_inside_proposal']} | {m['proposal_intervals_with_a_return']}/{m['total_proposal_intervals']} |"
                )
        lines += [
            "",
            "Nearby poses and compatible orientation do not establish shared scene; these counts only guide independent review.",
            "",
        ]
        if revisit.get("secondary_counts"):
            lines += [
                "### Secondary geometric connections",
                "",
                "| Method | Operationally accepted pairs | Accepted estimates within provisional pose tolerance |",
                "| --- | ---: | ---: |",
            ]
            for name, m in revisit["secondary_counts"].items():
                lines.append(
                    f"| {name} | {m['operational_accepted']} | {m['accepted_pose_within_provisional_tolerance']} |"
                )
            lines += [
                "",
                "These are geometric/pose diagnostics. Independently labeled real revisits are still required to call connections correct loops.",
                "",
            ]
    if result.get("independent_event_suite"):
        lines += [
            "## Equal-sequence independent event aggregate",
            "",
            "| K | Method | Metric | Mean | Available sequences |",
            "| --- | --- | --- | --- | --- |",
        ]
        for k, methods in result["independent_event_suite"].items():
            for name, metrics in methods.items():
                for metric, m in metrics.items():
                    lines.append(
                        f"| {k} | {name} | {metric} | {value(m['equal_sequence_mean'])} | {m['available_sequences']}/{m['total_sequences']} |"
                    )
        lines += ["", "Unavailable sequences withhold the overall mean.", ""]
    if result.get("equal_sequence_metrics"):
        lines += [
            "## Equal-sequence aggregate",
            "",
            "| K | Method | Metric | Mean | Available sequences |",
            "| --- | --- | --- | --- | --- |",
        ]
    if result.get("verified_equal_sequence_metrics"):
        lines += [
            "## Equal-sequence verified-loop aggregate",
            "",
            "| K | Method | Metric | Mean | Available sequences |",
            "| --- | --- | --- | --- | --- |",
        ]
        for k, methods in result["verified_equal_sequence_metrics"].items():
            for method, metrics in methods.items():
                for metric, row in metrics.items():
                    lines.append(
                        f"| {k} | {method} | {metric} | {value(row['equal_sequence_mean'])} | {row['available_sequences']}/{row['total_sequences']} |"
                    )
        for k, methods in result["equal_sequence_metrics"].items():
            for method, metrics in methods.items():
                for metric, row in metrics.items():
                    lines.append(
                        f"| {k} | {method} | {metric} | {value(row['equal_sequence_mean'])} | {row['available_sequences']}/{row['total_sequences']} |"
                    )
        lines += [
            "",
            "Missing sequence metrics withhold the overall mean instead of silently dropping that sequence.",
            "",
        ]
    if result.get("reference_geometry"):
        from tasks.reference_geometry.reporting import render

        lines += render(result["reference_geometry"])
    if result.get("connection_diagnostics"):
        from ..connection_diagnostics import render_diagnostics

        lines += render_diagnostics(result["connection_diagnostics"])
    if result.get("reference_geometry", {}).get("mode") == "reference_features":
        lines += [
            "## Provenance and limitations",
            "",
            "The companion JSON and artifact directory retain original detector evidence hashes, reference hashes, per-feature world coordinates and numerical errors. No operational acceptance or fitted pose is measured in this experiment.",
            "",
            "This short synthetic pilot does not establish full SLAM trajectory improvement or generalization.",
            "",
        ]
        return "\n".join(lines)
    if result.get("reference_geometry"):
        lines += [
            "## Provenance and limitations",
            "",
            "Configuration references, per-query and per-feature evidence, reference hashes and interval availability are retained in the companion JSON and benchmark artifact directory.",
            "",
            "Candidate returns, accepted camera-derived constraints, reference overlap labels and pose errors are separate measurements. Full SLAM trajectory improvement and generalization are not established.",
            "",
        ]
        return "\n".join(lines)
    lines += [
        "## Provenance and limitations",
        "",
        "Full configurations, per-query measurements, paired block intervals, label hashes and feature aggregates are in the companion JSON.",
        "",
        "Counts are image pairs and feature observations, not accepted SLAM constraints. This sequence alone cannot establish generalization.",
        "",
    ]
    return "\n".join(lines)
