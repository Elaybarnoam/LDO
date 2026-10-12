"""Timestamped human and machine reports through the shared evaluation writer."""

import shutil
from pathlib import Path

from tasks.loop_closure.comparison.cli import publish_report
from tasks.loop_closure.comparison.reference import sha256

from .develop import ROOT


def percent(value):
    return "Unavailable" if value is None else f"{value:.1%}"


def render(result):
    event_retention = result["steps"]["2"]["confirmed_event_retention"]
    if event_retention is None:
        policy_summary = "Event-retention performance cannot be established because the baseline has no confirmed event hits."
    elif event_retention < 0.9:
        policy_summary = "Candidate filtering failed that event-retention floor on this held-out environment; keep it experimental and prefer confidence-only for this pilot. No parameters were retuned on these test results."
    else:
        policy_summary = "Candidate filtering met the event-retention floor in this test; broader validation is still needed."
    lines = [
        "# LDO sequential optimization experiment",
        "",
        f"Test environment: **{result['test_environment']}**; {len(result['test_trajectories'])} trajectories.",
        "",
        "Training: RetroOffice. Development: ArchVizTinyHouseDay. All choices frozen before CountryHouse model evaluation; no test-driven tuning.",
        "",
        "## Held-out results",
        "",
        "Correct/incorrect below refer to individual feature correspondences under the unchanged reference-depth/pose gates. Unknown is not incorrect.",
        "",
        "| Variant | Correct feature matches | Incorrect feature matches | Unknown | Correct among judgeable |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    orb = result["orb"]["orb"]
    rows = [
        (
            "ORB + DBoW2",
            {
                "features": {
                    "supported": orb["supported"],
                    "contradicted": orb["contradicted"],
                    "untestable": orb["untestable"],
                    "supported_among_judgeable": orb["support_among_judgeable"],
                    "judgeable_fraction": orb["judgeable_fraction"],
                    "supported_fraction_bounds": orb["support_fraction_bounds"],
                },
                "candidates": orb["retrieval"],
            },
        )
    ]
    rows.extend((k, v) for k, v in result["variants"].items() if k != "development_selected")
    for name, value in rows:
        if value is None:
            continue
        f = value["features"]
        lines.append(
            f"| {name} | {f['supported']} | {f['contradicted']} | {f['untestable']} | {percent(f['supported_among_judgeable'])} |"
        )
    lines += [
        "",
        "### Candidate image pairs and confirmed revisit events",
        "",
        "A correct candidate satisfies the frozen 20% bidirectional visible-overlap rule. These counts are separate from individual feature correctness and from pose accuracy.",
        "",
        "| Variant | Correct candidate pairs | False candidate pairs | Unknown pairs | Confirmed event hits |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for name, value in rows:
        if value is None:
            continue
        c = value["candidates"]
        lines.append(
            f"| {name} | {c['true_positive_pairs']} | {c['false_positive_pairs']} | {c['unknown_pairs']} | {c['detected_confirmed_events']}/{c['confirmed_events']} |"
        )
    lines += [
        "",
        "### Reference coverage and unknown bounds",
        "",
        "| Variant | Judgeable matches | Correct fraction bounds over all reported matches |",
        "| --- | ---: | --- |",
    ]
    for name, value in rows:
        if value is None:
            continue
        features = value["features"]
        bounds = features["supported_fraction_bounds"]
        interval = f"{percent(bounds[0])}–{percent(bounds[1])}" if bounds else "Unavailable"
        lines.append(f"| {name} | {percent(features['judgeable_fraction'])} | {interval} |")
    lines += [
        "",
        "## Each change against its predecessor",
        "",
        "| Step | Correct matches retained | Incorrect matches removed | True candidates retained | False candidates removed | Confirmed event hits retained |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, delta in result["steps"].items():
        if delta is not None:
            lines.append(
                f"| {name} | {percent(delta['supported_match_retention'])} | {delta['contradicted_matches_removed']} | {percent(delta['true_candidate_retention'])} | {delta['false_candidates_removed']} | {percent(delta['confirmed_event_retention'])} |"
            )
    lines += [
        "",
        "Negative removals mean more errors. Retention above 100% means more correct matches or candidates. Event hits are over confirmed reference events, not overall recall with unknown labels.",
        "",
        "## Interpretation",
        "",
        f"Confidence filtering retained {percent(result['steps']['1']['supported_match_retention'])} of correct feature matches and removed {result['steps']['1']['contradicted_matches_removed']} incorrect matches.",
        "",
        f"Candidate filtering retained {percent(result['steps']['2']['true_candidate_retention'])} of known correct candidates and {percent(result['steps']['2']['confirmed_event_retention'])} of confirmed event hits. The predeclared event-retention floor is 90%.",
        "",
        policy_summary,
        "",
        "## Fine-tuning decision",
        "",
        f"Adapted head promoted on development: **{result['development']['training_promoted']}**. The full-depth pretrained control separates learning from a change in inference computation.",
        "",
        "## Limits",
        "",
        "ORB is the original unfiltered K=5 baseline. The LDO candidate policy can abstain, so fewer false returns alone do not establish superiority over a similarly calibrated ORB detector. Compare retained true candidates and event hits alongside errors.",
        "",
    ]
    lines.extend(f"- {text}" for text in result["limitations"])
    lines += [
        "",
        f"Baseline evidence: `{result['baseline_report']}`",
        "",
        f"Freeze manifest SHA256: `{result['freeze_manifest_sha256']}`",
        "",
    ]
    return "\n".join(lines)


def publish(result, config):
    result["optimization_source_sha256"] = {
        p.name: sha256(p) for p in Path(__file__).parent.glob("*.py")
    }
    path = publish_report(
        {"sequence": result["test_environment"], "optimization": result},
        ROOT / "evaluation/output",
        config,
    )
    source = path.with_suffix("") / "source/optimization"
    source.mkdir()
    for item in Path(__file__).parent.glob("*.py"):
        shutil.copyfile(item, source / item.name)
    return path
