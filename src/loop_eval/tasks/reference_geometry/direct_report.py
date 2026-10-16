"""Reports for direct model evaluation: no operational acceptance or fitted pose."""

from collections import Counter


def aggregate(sequences, k):
    result = {}
    for method in ("orb", "ldo"):
        counts = Counter()
        for sequence in sequences:
            counts.update(
                {
                    key: sequence["features"][method][key]
                    for key in ("supported", "contradicted", "untestable", "zero_match_pairs")
                }
            )
        supported, bad, unknown = (
            counts[key] for key in ("supported", "contradicted", "untestable")
        )
        judged, total = supported + bad, supported + bad + unknown
        rows = [s["retrieval"][str(k)][method] for s in sequences]
        pairs = sum(r["returned_pairs"] for r in rows)
        result[method] = {
            **dict(counts),
            "reported_matches": total,
            "returned_pairs": pairs,
            "judgeable_fraction": judged / total if total else None,
            "support_among_judgeable": supported / judged if judged else None,
            "contradiction_among_judgeable": bad / judged if judged else None,
            "support_fraction_bounds": [supported / total, (supported + unknown) / total]
            if total
            else None,
            "contradiction_fraction_bounds": [bad / total, (bad + unknown) / total]
            if total
            else None,
            "supported_per_returned_pair": supported / pairs if pairs else None,
            "retrieval": {
                key: sum(r[key] for r in rows)
                for key in (
                    "true_positive_pairs",
                    "false_positive_pairs",
                    "unknown_pairs",
                    "confirmed_events",
                    "detected_confirmed_events",
                )
            },
        }
    return result


def render(task):
    def pct(value):
        return "Unavailable" if value is None else f"{value:.1%}"

    policy = task["manifest"]["protocol"]
    k = policy["top_k"]
    rows = aggregate(task["sequences"], k)
    lines = [
        "## Direct reference-depth evaluation",
        "",
        "Every reported feature assignment is checked using TartanAir reference depth and camera poses. No learned stereo estimation, PnP, RANSAC, operational verifier or pose acceptance filter is used. The detector outputs are unchanged; ground truth is evaluator-only.",
        "",
        "| Method | Candidate pairs | Reported feature matches | Supported | Contradicted | Unknown | Judgeable coverage | Correct among judgeable |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, r in rows.items():
        lines.append(
            f"| {name} | {r['returned_pairs']} | {r['reported_matches']} | {r['supported']} | {r['contradicted']} | {r['untestable']} | {pct(r['judgeable_fraction'])} | {pct(r['support_among_judgeable'])} |"
        )
    lines += [
        "",
        f"Reference support requires XYZ distance <= max({policy['feature_xyz_tolerance_m']:g} m, {policy['feature_xyz_relative_tolerance']:g} times maximum endpoint depth) and symmetric reprojection error <= {policy['feature_pixel_tolerance']:g} pixels, with usable reference depth at both endpoints.",
        "",
    ]
    lines += [
        "",
        "Contradicted means the reported feature locations disagree under the frozen XYZ/reprojection tolerances. Unknown features are not false positives. These are feature-correspondence judgments, not counts of false loop closures. A different number of assignments and unknown coverage prevents a conclusion from absolute counts alone.",
        "",
        "### Bounds including unknown feature matches",
        "",
        "| Method | Supported fraction bounds | Contradicted fraction bounds | Zero-match candidate pairs |",
        "| --- | --- | --- | ---: |",
    ]
    for name, r in rows.items():

        def bounds(values):
            return "Unavailable" if values is None else f"{pct(values[0])} to {pct(values[1])}"

        lines.append(
            f"| {name} | {bounds(r['support_fraction_bounds'])} | {bounds(r['contradiction_fraction_bounds'])} | {r['zero_match_pairs']} |"
        )
    lines += [
        "",
        f"### Independent image-pair retrieval (K={k})",
        "",
        "| Method | Overlap-positive | Overlap-negative | Unknown | Confirmed event runs reached |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for name, r in rows.items():
        v = r["retrieval"]
        lines.append(
            f"| {name} | {v['true_positive_pairs']} | {v['false_positive_pairs']} | {v['unknown_pairs']} | {v['detected_confirmed_events']}/{v['confirmed_events']} |"
        )
    lines += [
        "",
        f"Image-pair labels use the frozen {policy['loop_overlap']:.0%} bidirectional surface-overlap policy, independently of reported feature matches. Event hits cover confirmed runs only; overall recall is withheld when the reference universe is incomplete.",
        "",
        "### Unknown reference depth: first failing gate",
        "",
        "| Method | Outside/invalid pixel | Nonfinite depth | Depth outside range | Depth boundary |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for name, r in task.get("depth_coverage", {}).items():
        c = r["untestable"]
        lines.append(
            f"| {name} | {c.get('outside_image_or_nonfinite_pixel', 0)} | {c.get('nonfinite_depth', 0)} | {c.get('depth_out_of_range', 0)} | {c.get('depth_boundary', 0)} |"
        )
    lines += [
        "",
        "### Per-trajectory feature judgments",
        "",
        "| Trajectory | Method | Supported | Contradicted | Unknown |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for sequence in task["sequences"]:
        for name, r in sequence["features"].items():
            lines.append(
                f"| {sequence['trajectory']} | {name} | {r['supported']} | {r['contradicted']} | {r['untestable']} |"
            )
    lines += [
        "",
        "Depth sampling, uncertainty masks and numerical tolerances remain frozen. This is a short synthetic pilot in one environment, using each detector's own returned candidates. Static-world and pretrained training-overlap assumptions are unaudited. It establishes neither real-world superiority nor OOD performance. Historical operational pose-failure counts are not measurements in this experiment.",
        "",
    ]
    return lines
