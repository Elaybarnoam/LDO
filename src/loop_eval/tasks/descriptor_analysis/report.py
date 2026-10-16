"""Readable descriptor evidence with explicit limits on causal attribution."""


def percentage(n, d):
    return f"{100 * n / d:.1f}%" if d else "N/A"


def render(result: dict) -> str:
    lines = [
        "# LDO descriptor and assignment analysis",
        "",
        "Frozen SuperPoint/LightGlue confidence-0.3 baseline. Development data only; "
        "TartanAir provides ground-truth depth and poses. No inference, training or promotion occurred.",
        "",
        "## Rank-restricted geometric capacity",
        "",
        "A usable pair has at least 20 reference-supported one-to-one correspondences. "
        "This is a diagnostic, not SLAM acceptance. Top-k restricts the SAME supported "
        "edge's raw descriptor cosine ranks; reciprocal requires both directions.",
        "",
        "| Split / scene | Pairs | Baseline usable | Geometry capacity ≥20 | "
        "Reciprocal top-1 ≥20 | Reciprocal top-5 ≥20 | Reciprocal top-10 ≥20 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for role, group in result["development"].items():
        for scene, c in {"Overall": group["overall"], **group["scenes"]}.items():
            values = [
                f"{role} / {scene}",
                c["pairs"],
                c["baseline_usable_pairs"],
                c["oracle_usable_pairs"],
                c["reciprocal_top1_usable_pairs"],
                c["reciprocal_top5_usable_pairs"],
                c["reciprocal_top10_usable_pairs"],
            ]
            lines.append("| " + " | ".join(map(str, values)) + " |")
    lines += [
        "",
        "## Pairs the baseline could not make usable",
        "",
        "| Split | Gap pairs | Forward top-1 capacity ≥20 | Reciprocal top-1 ≥20 | "
        "Reciprocal top-5 ≥20 | Reciprocal top-10 ≥20 | Reciprocal top-50 ≥20 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for role, group in result["development"].items():
        c = group["overall"]
        values = [
            role,
            c["gap_pairs"],
            c["gap_forward_top1_usable_pairs"],
            *(c[f"gap_reciprocal_top{k}_usable_pairs"] for k in (1, 5, 10, 50)),
        ]
        lines.append("| " + " | ".join(map(str, values)) + " |")
    lines += ["", "## Missing associations", ""]
    for role, group in result["development"].items():
        c = group["overall"]
        n = c["missed_supported_queries"]
        lines += [
            f"### {role}",
            "",
            f"- {n:,} query features have a geometrically supported alternative but no supported "
            f"baseline assignment; {c['missed_unassigned_queries']:,} are unassigned.",
            "- Among those missing supported queries: "
            + ", ".join(
                f"{percentage(c[f'missed_supported_queries_top{k}'], n)} have a forward top-{k} alternative"
                for k in (1, 5, 10)
            )
            + ".",
            f"- {c['contradicted_with_higher_cosine_supported_alternative']:,}/"
            f"{c['reported_contradicted']:,} contradicted assignments have a higher-cosine "
            "supported alternative for the same query feature.",
            "",
        ]
    lines += [
        "## Interpretation limits",
        "",
        "- Compatible geometry does not prove unique visual identity or visibility.",
        "- Raw SuperPoint similarity is not LightGlue's contextual assignment score. "
        "High raw ranks expose opportunities, not proof of a specific internal model bug.",
        "- Every keypoint competes in ranking, including those with unknown reference evidence.",
        "- Ties within 1e-7 receive the conservative worst tied rank.",
        "- These are selected positive development pairs; do not infer global false-loop precision.",
        "- No model accuracy improvement, event recovery or native SLAM acceptance is claimed.",
        "- New model choices require complete development replays, event-preserving promotion "
        "checks and a frozen fresh-environment test.",
        "",
        "## Provenance",
        "",
        f"- Freeze SHA256: `{result['freeze_sha256']}`",
        f"- Artifact root: `{result['artifact_root']}`",
        "- Per-pair NPZ records supported-edge ranks, actual-assignment ranks and cosine scores.",
        "- Inputs, descriptors, geometry edges and original assignments were hash checked.",
    ]
    return "\n".join(lines) + "\n"
