"""Independent review proposals, append-only decisions and immutable snapshots."""

import json
import shutil
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import yaml

from ..comparison.reference import load_reference, prepare, sha256, write_json


def load_policy(path: Path) -> dict:
    p = yaml.safe_load(path.read_text(encoding="utf-8"))
    expected = {
        "version",
        "proposal_distance_m",
        "proposal_orientation_degrees",
        "event_maximum_query_gap_ns",
        "positive_reviewers",
        "hard_negative_reviewers",
        "ordinary_negative_reviewers",
        "target_precision",
        "development_sequences",
        "held_out_sequences",
        "threshold_status",
    }
    if not isinstance(p, dict) or set(p) != expected or p["version"] != 1:
        raise ValueError("Invalid revisit policy")
    for key in (
        "event_maximum_query_gap_ns",
        "positive_reviewers",
        "hard_negative_reviewers",
        "ordinary_negative_reviewers",
    ):
        if type(p[key]) is not int or p[key] < 1:
            raise ValueError("Invalid revisit integer policy")
    for key in ("proposal_distance_m", "proposal_orientation_degrees", "target_precision"):
        if type(p[key]) not in (int, float) or not np.isfinite(p[key]) or p[key] <= 0:
            raise ValueError("Invalid revisit numeric policy")
    if p["proposal_orientation_degrees"] > 180 or p["target_precision"] > 1:
        raise ValueError("Invalid angular/precision range")
    for key in ("development_sequences", "held_out_sequences"):
        if (
            not isinstance(p[key], list)
            or not p[key]
            or any(not isinstance(s, str) or not s for s in p[key])
            or len(set(p[key])) != len(p[key])
        ):
            raise ValueError("Invalid sequence split")
    if set(p["development_sequences"]) & set(p["held_out_sequences"]):
        raise ValueError("Development and held-out sequences overlap")
    return p


def proposed(item: dict, policy: dict) -> bool:
    aid = item.get("pose_review_aid", {})
    return bool(
        aid.get("available")
        and aid["camera_position_distance_m"] <= policy["proposal_distance_m"]
        and aid["camera_orientation_difference_degrees"] <= policy["proposal_orientation_degrees"]
    )


def intervals(stamps: list[int], gap_ns: int) -> list[list[int]]:
    groups = []
    for stamp in sorted(set(stamps)):
        if not groups or stamp - groups[-1][-1] > gap_ns:
            groups.append([stamp])
        else:
            groups[-1].append(stamp)
    return groups


def prepare_revisits(config: dict, policy_path: Path) -> dict:
    if config["protocol"]["query_stride"] != 1:
        raise ValueError("Event reference must include every replay query")
    policy = load_policy(policy_path)
    root = Path(config["reference"]["root"])
    prepare(
        Path(config["reference"]["sequence"]),
        Path(config["reference"]["replay"]),
        root,
        config["protocol"],
    )
    shutil.copyfile(policy_path, root / "policy.yaml")
    manifest, records = load_reference(root)
    by_query = defaultdict(list)
    for (q, h), item in records.items():
        if proposed(item, policy):
            by_query[q].append(h)
    proposals = []
    for i, group in enumerate(intervals(list(by_query), policy["event_maximum_query_gap_ns"]), 1):
        proposals.append(
            {
                "proposal_id": i,
                "label": "unknown",
                "is_ground_truth": False,
                "query_start_ns": group[0],
                "query_end_ns": group[-1],
                "historical_intervals": [
                    [x[0], x[-1]]
                    for x in intervals(
                        [h for q in group for h in by_query[q]],
                        policy["event_maximum_query_gap_ns"],
                    )
                ],
                "pair_count": sum(len(by_query[q]) for q in group),
                "pairs": [[q, h] for q in group for h in by_query[q]],
            }
        )
    with (root / "proposals.jsonl").open("x", encoding="utf-8") as stream:
        for proposal in proposals:
            stream.write(json.dumps(proposal) + "\n")
    result = {
        "sequence": manifest["sequence"],
        "reference_pairs": len(records),
        "pose_admitted_queries": len(manifest["queries"]),
        "queries_with_eligible_history": sum(
            q["eligible_history"] > 0 for q in manifest["queries"]
        ),
        "excluded_queries_missing_pose": len(manifest["excluded_queries_missing_pose"]),
        "pose_proposed_pairs": sum(p["pair_count"] for p in proposals),
        "proposal_intervals": len(proposals),
        "proposals_are_labels": False,
        "independent_reviews": 0,
        "policy_sha256": sha256(root / "policy.yaml"),
        "proposals_sha256": sha256(root / "proposals.jsonl"),
    }
    write_json(root / "preparation.json", result)
    return result


def validate_review(review: dict, records: dict) -> list[tuple[int, int]]:
    keys = {
        "query_start_ns",
        "query_end_ns",
        "historical_start_ns",
        "historical_end_ns",
        "label",
        "reviewer",
        "reason",
        "reviewed_at",
        "detector_blind",
    }
    if (
        not keys <= set(review) <= keys | {"hard_negative"}
        or review["label"] not in {"loop", "non_loop", "unknown"}
        or review["detector_blind"] is not True
    ):
        raise ValueError("Invalid independent interval review")
    if any(not isinstance(review[k], str) or not review[k].strip() for k in ("reviewer", "reason")):
        raise ValueError("Reviewer and justification required")
    if not isinstance(review["reviewed_at"], str):
        raise ValueError("Review timestamp must be an ISO string")
    if "hard_negative" in review and type(review["hard_negative"]) is not bool:
        raise ValueError("Hard-negative flag must be boolean")
    when = datetime.fromisoformat(review["reviewed_at"])
    if when.utcoffset() is None:
        raise ValueError("Review timestamp requires timezone")
    for start, end in (
        ("query_start_ns", "query_end_ns"),
        ("historical_start_ns", "historical_end_ns"),
    ):
        if (
            type(review[start]) is not int
            or type(review[end]) is not int
            or review[start] > review[end]
        ):
            raise ValueError("Invalid review timestamp interval")
    selected = [
        key
        for key in records
        if review["query_start_ns"] <= key[0] <= review["query_end_ns"]
        and review["historical_start_ns"] <= key[1] <= review["historical_end_ns"]
    ]
    if not selected:
        raise ValueError("Review rectangle contains no eligible reference pairs")
    query_stamps, history_stamps = ({q for q, _ in selected}, {h for _, h in selected})
    if (
        review["query_start_ns"] not in query_stamps
        or review["query_end_ns"] not in query_stamps
        or review["historical_start_ns"] not in history_stamps
        or review["historical_end_ns"] not in history_stamps
    ):
        raise ValueError("Review boundaries must be admissible replay frames")
    return selected


def append_review(root: Path, review: dict) -> None:
    _, records = load_reference(root)
    validate_review(review, records)
    with (root / "interval_reviews.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(review, allow_nan=False) + "\n")


def consensus(records: dict, reviews: list[dict], policy: dict) -> tuple[dict, dict]:
    latest = defaultdict(dict)
    for review in reviews:
        for pair in validate_review(review, records):
            latest[pair][review["reviewer"]] = review
    labels, states = {}, Counter()
    for pair, item in records.items():
        decisions = list(latest[pair].values())
        decisive = [d for d in decisions if d["label"] != "unknown"]
        votes = {d["label"] for d in decisive}
        required = (
            policy["positive_reviewers"]
            if votes == {"loop"}
            else policy["hard_negative_reviewers"]
            if proposed(item, policy) or any(d.get("hard_negative", False) for d in decisions)
            else policy["ordinary_negative_reviewers"]
        )
        if not decisive:
            label, state = "unknown", "unreviewed_or_explicit_unknown"
        elif len(votes) > 1:
            label, state = "unknown", "reviewer_disagreement"
        elif len(decisive) < required or any(d["label"] == "unknown" for d in decisions):
            label, state = "unknown", "needs_independent_review"
        else:
            label, state = decisive[0]["label"], "reviewed_consensus"
        labels[pair] = {
            **item,
            "label": label,
            "review_state": state,
            "reviewers": sorted(latest[pair]),
        }
        states[state] += 1
    return labels, dict(states)


def freeze(root: Path, output: Path) -> dict:
    policy = load_policy(root / "policy.yaml")
    preparation = json.loads((root / "preparation.json").read_text())
    if (
        sha256(root / "policy.yaml") != preparation["policy_sha256"]
        or sha256(root / "proposals.jsonl") != preparation["proposals_sha256"]
    ):
        raise ValueError("Reference proposal policy changed")
    manifest, records = load_reference(root)
    journal = root / "interval_reviews.jsonl"
    reviews = []
    if journal.exists():
        with journal.open(encoding="utf-8") as stream:
            reviews = [json.loads(line) for line in stream]
    resolved, states = consensus(records, reviews, policy)
    output.mkdir(parents=True, exist_ok=False)
    for name in ("pairs.jsonl", "policy.yaml", "proposals.jsonl", "preparation.json"):
        shutil.copyfile(root / name, output / name)
    if journal.exists():
        shutil.copyfile(journal, output / "interval_reviews.jsonl")
    with (output / "reviews.jsonl").open("x", encoding="utf-8") as stream:
        for pair, item in resolved.items():
            if item["label"] != "unknown":
                stream.write(
                    json.dumps(
                        {
                            "query_timestamp_ns": pair[0],
                            "historical_timestamp_ns": pair[1],
                            "label": item["label"],
                            "reviewer": "; ".join(item["reviewers"]),
                            "reason": "Independent interval consensus; original rationales in frozen interval journal",
                        }
                    )
                    + "\n"
                )
    from .metrics import build_events

    events = build_events(
        resolved,
        [q["timestamp_ns"] for q in manifest["queries"]],
        policy["event_maximum_query_gap_ns"],
    )
    write_json(output / "events.json", events)
    snapshot = {
        **manifest,
        "freeze": {
            "version": 1,
            "frozen_at": datetime.now(UTC).isoformat(),
            "source_manifest_sha256": sha256(root / "manifest.json"),
            "labels": dict(Counter(p["label"] for p in resolved.values())),
            "review_states": states,
            "interval_reviews": len(reviews),
            "confirmed_events": len(events),
            "files_sha256": {
                name: sha256(output / name)
                for name in (
                    "pairs.jsonl",
                    "reviews.jsonl",
                    "policy.yaml",
                    "proposals.jsonl",
                    "preparation.json",
                    "events.json",
                )
                + (("interval_reviews.jsonl",) if journal.exists() else ())
            },
        },
    }
    write_json(output / "manifest.json", snapshot)
    return snapshot["freeze"]


def load_frozen(root: Path) -> tuple[dict, dict, dict, list]:
    manifest, records = load_reference(root)
    frozen = manifest.get("freeze")
    if not frozen or frozen.get("version") != 1:
        raise ValueError("Evaluation requires an immutable frozen revisit reference")
    for name, expected in frozen["files_sha256"].items():
        if sha256(root / name) != expected:
            raise ValueError("Frozen reference changed")
    policy = load_policy(root / "policy.yaml")
    events = json.loads((root / "events.json").read_text())
    return manifest, records, policy, events
