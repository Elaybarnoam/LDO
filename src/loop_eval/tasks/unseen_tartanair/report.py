"""Separate candidate/event and feature evidence in the unseen-environment report."""

import shutil
from pathlib import Path

from loop_eval.paths import project_root
from loop_eval.tasks.loop_closure.comparison.cli import publish_report
from loop_eval.tasks.loop_closure.comparison.reference import sha256

ROOT = project_root()


def pct(value):
    return "Unavailable" if value is None else f"{value:.1%}"


def interval(low, high):
    return f"{pct(low)} to {pct(high)}"


def event_hits(row):
    count = row["confirmed_events"]
    return f"{row['detected_confirmed_events']}/{count}" if count else "N/A (no confirmed events)"


def render(result):
    rows = [(item["environment"], item["task"]["aggregate"]) for item in result["environments"]]
    rows.append(("Combined", result["aggregate"]))
    lines = [
        "# LDO versus ORB: unseen TartanAir environments",
        "",
        "Frozen confidence-only LDO: MegaLoc + SuperPoint + LightGlue, threshold 0.3. No candidate filter, adapted weights, training or tuning on these environments.",
        "",
        "Both models receive identical grayscale cam0 frames, approximately 2 Hz, K=5 and a 5-second temporal exclusion. Each trajectory starts with an empty retrieval history. Neither detector consumes IMU or ground truth.",
        "",
        "## Candidate image pairs and revisit events",
        "",
        "Correct/false candidate labels use the frozen 20% minimum bidirectional visible surface-overlap rule. These are not accepted SLAM loops or pose-error counts. Event hits measure retrieval only: they do not require successful feature matching or an accepted pose.",
        "",
        "| Environment | Detector | Correct pairs | False pairs | Unknown pairs | Confirmed event hits |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    for environment, methods in rows:
        for method, value in methods.items():
            r = value["retrieval"]
            lines.append(
                f"| {environment} | {method} | {r['true_positive_pairs']} | {r['false_positive_pairs']} | {r['unknown_pairs']} | {event_hits(r)} |"
            )
    lines += [
        "",
        "### Candidate precision with unknown bounds",
        "",
        "| Environment | Detector | Precision among known labels | Precision bounds including unknowns |",
        "| --- | --- | ---: | --- |",
    ]
    for environment, methods in rows:
        for method, value in methods.items():
            r = value["retrieval"]
            tp, fp, unknown = (
                r["true_positive_pairs"],
                r["false_positive_pairs"],
                r["unknown_pairs"],
            )
            total = tp + fp + unknown
            known = tp / (tp + fp) if tp + fp else None
            bounds = interval(tp / total, (tp + unknown) / total) if total else "Unavailable"
            lines.append(f"| {environment} | {method} | {pct(known)} | {bounds} |")
    lines += [
        "",
        "## Individual feature correspondences",
        "",
        "Reference depth and camera poses independently judge every reported match. Correct means usable depths at both pixels, symmetric reprojection <=3 px, and XYZ distance <=max(0.05 m, 0.005 times maximum endpoint depth). Unknown depth evidence is never classified as incorrect.",
        "",
        "| Environment | Detector | Correct matches | Incorrect matches | Unknown matches | Correct among judgeable | Judgeable coverage |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for environment, methods in rows:
        for method, r in methods.items():
            lines.append(
                f"| {environment} | {method} | {r['supported']} | {r['contradicted']} | {r['untestable']} | {pct(r['support_among_judgeable'])} | {pct(r['judgeable_fraction'])} |"
            )
    lines += [
        "",
        "### Correct-feature fraction bounds over all reported matches",
        "",
        "| Environment | Detector | Bounds including unknowns |",
        "| --- | --- | --- |",
    ]
    for environment, methods in rows:
        for method, r in methods.items():
            bounds = r["support_fraction_bounds"]
            lines.append(
                f"| {environment} | {method} | {interval(*bounds) if bounds else 'Unavailable'} |"
            )
    lines += [
        "",
        "## Per-trajectory candidate results",
        "",
        "| Environment | Trajectory | Detector | Correct pairs | False pairs | Unknown pairs | Confirmed event hits |",
        "| --- | --- | --- | ---: | ---: | ---: | --- |",
    ]
    for environment in result["environments"]:
        for sequence in environment["task"]["sequences"]:
            for method, r in sequence["retrieval"][str(result["protocol"]["top_k"])].items():
                lines.append(
                    f"| {environment['environment']} | {sequence['trajectory']} | {method} | {r['true_positive_pairs']} | {r['false_positive_pairs']} | {r['unknown_pairs']} | {event_hits(r)} |"
                )
    lines += [
        "",
        "## Per-trajectory feature results",
        "",
        "| Environment | Trajectory | Detector | Correct matches | Incorrect matches | Unknown matches | Correct among judgeable |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for environment in result["environments"]:
        for sequence in environment["task"]["sequences"]:
            for method, r in sequence["features"].items():
                judged = r["supported"] + r["contradicted"]
                precision = r["supported"] / judged if judged else None
                lines.append(
                    f"| {environment['environment']} | {sequence['trajectory']} | {method} | {r['supported']} | {r['contradicted']} | {r['untestable']} | {pct(precision)} |"
                )
    lines += [
        "",
        "## Interpretation limits",
        "",
        "- These environments were unused in our own development; upstream pretrained exposure and shared synthetic assets are unaudited.",
        "- Unknown reference evidence can differ between methods. Judgeable precision is not accuracy across all reported matches; compare the bounds and coverage.",
        "- A smaller absolute count of wrong feature matches is not a fair error-rate comparison when output densities differ.",
        "- Confirmed-event hits do not establish overall recall when reference labels are incomplete. Redundant pairs do not count as additional events.",
        "- The unchanged 50 m depth limit and depth-boundary gates can reduce outdoor reference coverage. They were not retuned on these test scenes.",
        "- The original EuRoC XYZ evaluator is unchanged. This experiment uses simulator reference depth directly; no stereo estimator, RANSAC, PnP or operational verifier is involved.",
        "- No latency, real-world superiority, or downstream SLAM trajectory improvement is established here.",
        "",
        "## Provenance",
        "",
        f"Freeze SHA256: `{result['freeze_sha256']}`",
        "",
    ]
    for item in result["environments"]:
        lines += [
            f"- {item['environment']}: `{item['report']}` (SHA256 `{item['report_sha256']}`)."
        ]
    lines.append("")
    return "\n".join(lines)


def publish(result, config_path):
    result["report_source_sha256"] = sha256(Path(__file__))
    path = publish_report(
        {
            "sequence": " + ".join(e["environment"] for e in result["environments"]),
            "unseen_tartanair": result,
        },
        ROOT / "evaluation/output",
        config_path,
    )
    source = path.with_suffix("") / "source/unseen_tartanair"
    source.mkdir()
    for item in Path(__file__).parent.glob("*.py"):
        shutil.copyfile(item, source / item.name)
    return path
