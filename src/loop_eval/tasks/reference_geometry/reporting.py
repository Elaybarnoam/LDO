"""Pure aggregation and human-readable reporting, separate from inference."""

import json
from collections import Counter
from pathlib import Path

from loop_eval.tasks.loop_closure.comparison.metrics import read_trace
from loop_eval.tasks.loop_closure.comparison.reference import sha256
from loop_eval.tasks.loop_closure.revisits.metrics import evaluate


def audit_constraints(task):
    """Reconstruct the conjunction of pose accuracy and overlap from saved evidence."""
    policy = task["manifest"]["protocol"]
    for sequence in task["sequences"]:
        replay = Path(sequence["reference"]["root"])
        root = Path(task["artifact_directory"]) / sequence["trajectory"]
        for name, key in (
            ("reference.jsonl", "reference_sha256"),
            ("events.json", "events_sha256"),
        ):
            if sha256(replay / name) != sequence["reference"][key]:
                raise ValueError("Frozen reference changed before constraint audit")
        reference = {}
        for line in (replay / "reference.jsonl").read_text().splitlines():
            row = json.loads(line)
            reference[row["query_timestamp_ns"], row["historical_timestamp_ns"]] = row
        events = json.loads((replay / "events.json").read_text())
        queries = [row["timestamp_ns"] for row in json.loads((replay / "frames.json").read_text())]
        path = root / "connections.jsonl"
        if sha256(path) != sequence["artifact_hashes"]["connections"]:
            raise ValueError("Saved constraint evidence changed")
        accurate = {name: set() for name in ("orb", "ldo")}
        for line in path.read_text().splitlines():
            row = json.loads(line)
            if row["verification"]["status"] == "accepted" and row["pose_assessment"].get(
                "within_tolerance"
            ):
                accurate[row["method"]].add(
                    (row["query_timestamp_ns"], row["historical_timestamp_ns"])
                )
        for name in accurate:
            path = root / name / "retrieval.jsonl"
            if sha256(path) != sequence["artifact_hashes"][f"{name}_trace"]:
                raise ValueError("Saved detector trace changed")
            traces = read_trace(path, queries, policy["exclusion_ns"], policy["top_k"])
            sequence["connections"][name]["pose_consistent_independent_reference"] = evaluate(
                reference, traces, queries, events, policy["top_k"], accepted=accurate[name]
            )
    return task


def aggregate(sequences, k):
    result = {}
    for name in ("orb", "ldo"):
        rows = [s["retrieval"][str(k)][name] for s in sequences]
        counts = {
            key: sum(r[key] for r in rows)
            for key in (
                "true_positive_pairs",
                "false_positive_pairs",
                "unknown_pairs",
                "returned_pairs",
                "confirmed_events",
                "detected_confirmed_events",
            )
        }
        total = counts["returned_pairs"]
        counts["precision"] = (
            counts["true_positive_pairs"] / total if total and not counts["unknown_pairs"] else None
        )
        counts["precision_lower_bound"] = counts["true_positive_pairs"] / total if total else None
        counts["precision_upper_bound"] = (
            (counts["true_positive_pairs"] + counts["unknown_pairs"]) / total if total else None
        )
        counts["annotation_coverage_of_returns"] = (
            (counts["true_positive_pairs"] + counts["false_positive_pairs"]) / total
            if total
            else None
        )
        counts["event_recall"] = (
            counts["detected_confirmed_events"] / counts["confirmed_events"]
            if counts["confirmed_events"] and all(r["reference_complete"] for r in rows)
            else None
        )
        counts["known_event_recall_diagnostic"] = (
            counts["detected_confirmed_events"] / counts["confirmed_events"]
            if counts["confirmed_events"]
            else None
        )
        counts["feature_totals"] = dict(
            sum(
                (
                    Counter(
                        {
                            key: s["features"][name].get(key, 0)
                            for key in ("supported", "contradicted", "untestable")
                        }
                    )
                    for s in sequences
                ),
                Counter(),
            )
        )
        counts["accepted"] = sum(s["connections"][name]["accepted"] for s in sequences)
        counts["pose_consistent"] = sum(
            s["connections"][name]["pose_consistent"] for s in sequences
        )
        counts["pose_inconsistent"] = counts["accepted"] - counts["pose_consistent"]
        counts["accepted_reference"] = {
            key: sum(s["connections"][name]["independent_reference"][key] for s in sequences)
            for key in ("true_positive_pairs", "false_positive_pairs", "unknown_pairs")
        }
        audited = [
            s["connections"][name].get("pose_consistent_independent_reference") for s in sequences
        ]
        counts["jointly_confirmed_constraints"] = (
            sum(r["true_positive_pairs"] for r in audited)
            if all(r is not None for r in audited)
            else None
        )
        counts["jointly_confirmed_event_hits"] = (
            sum(r["detected_confirmed_events"] for r in audited)
            if all(r is not None for r in audited)
            else None
        )
        result[name] = counts
    return result


def render(task):
    if task.get("mode") == "reference_features":
        from .direct_report import render as render_features

        return render_features(task)
    task = {
        **task,
        "aggregate": aggregate(task["sequences"], task["manifest"]["protocol"]["top_k"]),
    }

    def fmt(value):
        return "Unavailable" if value is None else f"{value:.4f}"

    k = task["manifest"]["protocol"]["top_k"]
    assessment = task.get(
        "assessment_policy",
        {"maximum_translation_error_m": 0.2, "maximum_rotation_error_degrees": 5.0},
    )
    lines = [
        "## TartanAir V2 reference-geometry pilot",
        "",
        f"Raw candidate metrics use K={k}; these are retrieval proposals, not accepted loop closures. The exclusion is {task['manifest']['protocol']['exclusion_ns'] / 1e9:g} seconds. Source trajectories last 9 to 15 seconds, so this pilot does not test long-term revisits.",
        "",
        "Both detectors use identical grayscale cam0 frames. Reference depth/poses label outcomes only; operational verification uses observation stereo. IMU is installed but neither current detector consumes it.",
        "",
        "| Method | Candidate pairs | Correct under overlap policy | False under overlap policy | Unknown | Precision bounds | Events detected / reference | Event recall | Accepted / pose-consistent |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- |",
    ]
    for name, row in task["aggregate"].items():
        lines.append(
            f"| {name} | {row['returned_pairs']} | {row['true_positive_pairs']} | {row['false_positive_pairs']} | {row['unknown_pairs']} | {fmt(row['precision_lower_bound'])} to {fmt(row['precision_upper_bound'])} | {row['detected_confirmed_events']}/{row['confirmed_events']} | {fmt(row['event_recall'])} | {row['accepted']}/{row['pose_consistent']} |"
        )
    lines += [
        "",
        "Precision bounds assign every unknown return first as incorrect, then as correct. Overall event recall is unavailable when reference labels are incomplete; confirmed-event hits are a diagnostic subset.",
        "",
    ]
    lines += [
        "",
        "### First candidate only (K=1)",
        "",
        "| Method | Correct | False | Unknown | Precision bounds | Confirmed events detected |",
        "| --- | ---: | ---: | ---: | --- | --- |",
    ]
    for name, row in aggregate(task["sequences"], 1).items():
        lines.append(
            f"| {name} | {row['true_positive_pairs']} | {row['false_positive_pairs']} | {row['unknown_pairs']} | {fmt(row['precision_lower_bound'])} to {fmt(row['precision_upper_bound'])} | {row['detected_confirmed_events']}/{row['confirmed_events']} |"
        )
    lines += [
        "",
        "### Reference-depth feature checks",
        "",
        "| Method | Supported | Contradicted | Untestable | Judgeable fraction |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for name, row in task["aggregate"].items():
        counts = row["feature_totals"]
        total = sum(counts.values())
        lines.append(
            f"| {name} | {counts.get('supported', 0)} | {counts.get('contradicted', 0)} | {counts.get('untestable', 0)} | {fmt((counts.get('supported', 0) + counts.get('contradicted', 0)) / total if total else None)} |"
        )
    lines += [
        "",
        "Feature counts use each method's own returned candidates and reported assignments. They measure the complete approach, not an isolated matcher comparison; ORB retains its upstream extraction settings and LDO its pretrained configuration.",
        "",
    ]
    if task.get("depth_coverage"):
        lines += [
            "",
            "### Why reference depth cannot judge a feature match",
            "",
            "Counts use the first failing gate across either endpoint; each unknown match appears once.",
            "",
            "| Method | Outside / invalid pixel | Nonfinite depth | Depth outside range | Depth boundary |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
        for name, row in task["depth_coverage"].items():
            c = row["untestable"]
            lines.append(
                f"| {name} | {c.get('outside_image_or_nonfinite_pixel', 0)} | {c.get('nonfinite_depth', 0)} | {c.get('depth_out_of_range', 0)} | {c.get('depth_boundary', 0)} |"
            )
    lines += [
        "",
        "### Accepted constraints: separate revisit and pose checks",
        "",
        "| Method | Accepted | Overlap-positive | Overlap-negative | Overlap-unknown | Pose error exceeds tolerance |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, row in task["aggregate"].items():
        labels = row["accepted_reference"]
        lines.append(
            f"| {name} | {row['accepted']} | {labels['true_positive_pairs']} | {labels['false_positive_pairs']} | {labels['unknown_pairs']} | {row['pose_inconsistent']} |"
        )
    lines += [
        "",
        f"A pose failure means the estimated relative transform exceeds {assessment['maximum_translation_error_m']:g} m or {assessment['maximum_rotation_error_degrees']:g} degrees (provisional evaluation tolerances); it is not automatically a false revisit. An overlap-negative accepted constraint is false under the frozen 20% overlap policy, which is not proof that no physical surfaces are shared.",
        "",
    ]
    lines += [
        "",
        "### Constraints meeting both independent checks",
        "",
        "| Method | Pose-consistent and overlap-positive constraints | Confirmed event runs reached by these constraints |",
        "| --- | ---: | --- |",
    ]
    for name, row in task["aggregate"].items():
        count, hits = row["jointly_confirmed_constraints"], row["jointly_confirmed_event_hits"]
        lines.append(
            f"| {name} | {count if count is not None else 'Unavailable'} | {str(hits) + '/' + str(row['confirmed_events']) if hits is not None else 'Unavailable'} |"
        )
    lines += [
        "",
        "These are confirmed under the frozen overlap and provisional pose-error policies. Unknown pair labels remain unresolved, even if their pose estimate is accurate. Event hits cover the confirmed subset only.",
        "",
    ]
    lines += [
        "",
        f"### Per-trajectory candidate evaluation (K={k})",
        "",
        "| Trajectory | Method | Correct | False | Unknown | Events detected / reference |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    for sequence in task["sequences"]:
        for name, row in sequence["retrieval"][str(k)].items():
            lines.append(
                f"| {sequence['trajectory']} | {name} | {row['true_positive_pairs']} | {row['false_positive_pairs']} | {row['unknown_pairs']} | {row['detected_confirmed_events']}/{row['confirmed_events']} |"
            )
    lines += [
        "",
        "Labels measure a frozen minimum bidirectional visible-surface overlap, not manually established semantic place identity. Unknown reference coverage withholds overall recall. Continuous returns are not distinct events. This is a synthetic pilot in one environment, with unverified static-world assumptions and unaudited pretrained training overlap; it establishes neither OOD performance nor real-world superiority. Development-selected thresholds are not held-out results.",
        "",
    ]
    return lines
