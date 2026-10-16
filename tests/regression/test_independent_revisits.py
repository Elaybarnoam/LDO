"""Independent truth, event denominators and development/test separation."""

from copy import deepcopy
from pathlib import Path

import pytest

from loop_eval.tasks.loop_closure.comparison.reference import sha256, write_json
from loop_eval.tasks.loop_closure.revisits.metrics import (
    build_events,
    evaluate,
    paired_event_uncertainty,
)
from loop_eval.tasks.loop_closure.revisits.operating_points import (
    check_frozen_operating_points,
    select,
)
from loop_eval.tasks.loop_closure.revisits.reference import (
    consensus,
    freeze,
    load_frozen,
    load_policy,
    proposed,
    validate_review,
)


def policy():
    return load_policy(Path("configs/evaluation/loop_closure/revisits/policy.yaml"))


def reference(labels):
    return {
        (q, 0): {
            "query_timestamp_ns": q,
            "historical_timestamp_ns": 0,
            "label": label,
            "pose_review_aid": {
                "available": True,
                "camera_position_distance_m": 1.0,
                "camera_orientation_difference_degrees": 0.0,
            },
        }
        for q, label in labels.items()
    }


def review(q, label, reviewer):
    return {
        "query_start_ns": q,
        "query_end_ns": q,
        "historical_start_ns": 0,
        "historical_end_ns": 0,
        "label": label,
        "reviewer": reviewer,
        "reason": "Independently inspected physical scene",
        "reviewed_at": "2026-10-07T00:00:00+00:00",
        "detector_blind": True,
    }


def test_pose_proposals_never_create_labels_and_one_reviewer_is_not_consensus():
    records = reference({30: "unknown"})
    assert proposed(records[30, 0], policy())
    resolved, _ = consensus(records, [review(30, "loop", "a")], policy())
    assert resolved[30, 0]["label"] == "unknown"
    resolved, _ = consensus(records, [review(30, "loop", "a"), review(30, "loop", "a")], policy())
    assert resolved[30, 0]["label"] == "unknown"
    resolved, _ = consensus(records, [review(30, "loop", "a"), review(30, "loop", "b")], policy())
    assert resolved[30, 0]["label"] == "loop"


def test_disagreement_and_explicit_unknown_remain_unknown():
    records = reference({30: "unknown"})
    for label in ("non_loop", "unknown"):
        resolved, _ = consensus(
            records, [review(30, "loop", "a"), review(30, label, "b")], policy()
        )
        assert resolved[30, 0]["label"] == "unknown"
    resolved, _ = consensus(
        records,
        [review(30, "loop", "a"), review(30, "non_loop", "b"), review(30, "loop", "b")],
        policy(),
    )
    assert resolved[30, 0]["label"] == "loop"


def test_hard_negative_needs_independent_review_but_ordinary_negative_does_not():
    records = reference({30: "unknown"})
    resolved, _ = consensus(records, [review(30, "non_loop", "a")], policy())
    assert resolved[30, 0]["label"] == "unknown"
    records[30, 0]["pose_review_aid"]["camera_position_distance_m"] = 100
    resolved, _ = consensus(records, [review(30, "non_loop", "a")], policy())
    assert resolved[30, 0]["label"] == "non_loop"


@pytest.mark.parametrize("change", ["blind", "reason", "time", "bounds", "absent"])
def test_invalid_review_cannot_enter_reference(change):
    r = review(30, "loop", "a")
    if change == "blind":
        r["detector_blind"] = False
    elif change == "reason":
        r["reason"] = ""
    elif change == "time":
        r["reviewed_at"] = "2026-10-07T00:00:00"
    elif change == "bounds":
        r["query_start_ns"] = 29
    else:
        r["query_start_ns"] = r["query_end_ns"] = 99
    with pytest.raises(ValueError):
        validate_review(r, reference({30: "unknown"}))


def test_events_merge_frames_and_histories_but_do_not_bridge_unknowns():
    ref = reference({30: "loop", 31: "loop", 32: "unknown", 33: "loop"})
    ref[31, 1] = {"label": "loop"}
    events = build_events(ref, [30, 31, 32, 33], 10)
    assert len(events) == 2 and events[0]["query_timestamps"] == [30, 31]
    assert events[0]["historical_by_query"]["31"] == [0, 1]


def test_unreturned_event_stays_in_denominator_and_threshold_never_refills():
    ref = reference({30: "loop", 31: "loop", 32: "non_loop", 33: "loop"})
    ref[30, 1] = {"label": "non_loop"}
    events = build_events(ref, [30, 31, 32, 33], 10)
    traces = {
        30: [
            {"historical_timestamp_ns": 1, "score": 0.1},
            {"historical_timestamp_ns": 0, "score": 0.9},
        ],
        31: [],
        32: [],
        33: [],
    }
    m = evaluate(ref, traces, [30, 31, 32, 33], events, 2)
    assert m["event_recall"] == 0.5 and m["false_positive_pairs"] == 1
    assert evaluate(ref, traces, [30, 31, 32, 33], events, 1, 0.5)["detected_confirmed_events"] == 0
    ref[32, 0]["label"] = "unknown"
    m = evaluate(ref, traces, [30, 31, 32, 33], events, 2)
    assert m["event_recall"] is None and m["known_event_recall_diagnostic"] == 0.5


def test_operating_point_selected_on_full_truth_matches_direct_evaluation():
    ref = reference({30: "loop", 31: "non_loop", 32: "loop"})
    queries = [30, 31, 32]
    events = build_events(ref, queries, 10)
    traces = {
        30: [{"historical_timestamp_ns": 0, "score": 0.9}],
        31: [{"historical_timestamp_ns": 0, "score": 0.1}],
        32: [{"historical_timestamp_ns": 0, "score": 0.8}],
    }
    p = select(ref, traces, queries, events, 1, 1.0)
    assert p["available"] and p["score_threshold"] == 0.8 and p["development_event_recall"] == 1
    for row in p["sweep"]:
        direct = evaluate(ref, traces, queries, events, 1, row["score_threshold"])
        assert (
            row["precision"] == direct["precision"]
            and row["event_recall"] == direct["event_recall"]
        )
    ref[31, 0]["label"] = "unknown"
    assert not select(ref, traces, queries, events, 1, 0.99)["available"]


def test_frozen_thresholds_reject_test_leakage_or_settings_change():
    p = policy()
    artifact = {
        "version": 1,
        "available": True,
        "development_sequence": "MH_01_easy",
        "policy": p,
        "protocol": {},
        "configuration_fingerprints": {"model": "a"},
        "points": {
            "1": {
                "orb": {"available": True, "score_threshold": 0.5},
                "ldo": {"available": True, "score_threshold": 0.4},
            }
        },
    }
    check_frozen_operating_points(artifact, "V1_01_easy", p, {}, {"model": "a"})
    with pytest.raises(ValueError):
        check_frozen_operating_points(artifact, "MH_01_easy", p, {}, {"model": "a"})
    with pytest.raises(ValueError):
        check_frozen_operating_points(artifact, "V1_01_easy", p, {}, {"model": "b"})


def test_freeze_keeps_labels_unknown_and_snapshot_hash_protects_journal(tmp_path):
    import json
    import shutil

    root = tmp_path / "live"
    root.mkdir()
    records = reference({30: "unknown"})
    pair = records[30, 0]
    (root / "pairs.jsonl").write_text(json.dumps(pair) + "\n")
    (root / "proposals.jsonl").write_text("")
    shutil.copyfile("configs/evaluation/loop_closure/revisits/policy.yaml", root / "policy.yaml")
    write_json(
        root / "manifest.json",
        {
            "version": 1,
            "pair_count": 1,
            "pairs_sha256": sha256(root / "pairs.jsonl"),
            "queries": [{"timestamp_ns": 30}],
        },
    )
    write_json(
        root / "preparation.json",
        {
            "policy_sha256": sha256(root / "policy.yaml"),
            "proposals_sha256": sha256(root / "proposals.jsonl"),
        },
    )
    snapshot = tmp_path / "frozen"
    frozen = freeze(root, snapshot)
    assert frozen["labels"] == {"unknown": 1} and frozen["confirmed_events"] == 0
    assert load_frozen(snapshot)[1][30, 0]["label"] == "unknown"
    (snapshot / "reviews.jsonl").write_text(
        json.dumps(
            {
                "query_timestamp_ns": 30,
                "historical_timestamp_ns": 0,
                "label": "loop",
                "reviewer": "a",
                "reason": "changed",
            }
        )
        + "\n"
    )
    with pytest.raises(ValueError, match="Frozen reference changed"):
        load_frozen(snapshot)


def test_uncertainty_requires_complete_reference_and_multiple_event_blocks():
    ref = reference({i: "loop" if i % 2 == 0 else "non_loop" for i in range(10)})
    events = build_events(ref, list(range(10)), 2)
    traces = {i: [] for i in range(10)}
    a = evaluate(ref, traces, list(range(10)), events, 1)
    b = deepcopy(a)
    for e in b["per_event"]:
        e["detected"] = True
    m = paired_event_uncertainty(a, b, 0, 2, 100)
    assert m["interval_95"] == [1, 1]
    a["reference_complete"] = False
    assert not paired_event_uncertainty(a, b, 0, 2, 100)["available"]


def test_event_suite_keeps_unavailable_sequences_and_rejects_duplicates(tmp_path):
    import json

    from loop_eval.tasks.loop_closure.revisits.workflow import aggregate

    paths = []
    for sequence, value in (("one", 1.0), ("two", None)):
        metric = {"precision": value, "event_recall": value}
        report = {
            "status": "completed",
            "comparison_result": {
                "sequence": sequence,
                "protocol": {"k_values": [1]},
                "independent_revisits": {
                    "policy": policy(),
                    "configuration_fingerprints": {"model": "same"},
                    "metrics": {"1": {"orb": metric, "ldo": metric}},
                },
            },
        }
        path = tmp_path / f"{sequence}.json"
        write_json(path, report)
        paths.append(path)
    m = aggregate(paths)["independent_event_suite"]["1"]["ldo"]["event_recall"]
    assert m == {"equal_sequence_mean": None, "available_sequences": 1, "total_sequences": 2}
    with pytest.raises(ValueError, match="Duplicate"):
        aggregate([paths[0], paths[0]])
    changed = json.loads(paths[1].read_text())
    changed["comparison_result"]["independent_revisits"]["configuration_fingerprints"]["model"] = (
        "different"
    )
    paths[1].write_text(json.dumps(changed))
    with pytest.raises(ValueError, match="policies/configurations differ"):
        aggregate(paths)


def test_model_fingerprint_allows_new_dataset_but_freezes_algorithm_settings(tmp_path):
    import yaml

    from loop_eval.tasks.loop_closure.revisits.workflow import fingerprints

    orb = tmp_path / "orb.yaml"
    orb.write_text("version: 1\nsequence: MH_01_easy\nsample_hz: 2\ndataset_root: one\n")
    config = {
        "matching": {
            "orb_config": str(orb),
            "ldo_config": "configs/models/megaloc_lightglue.yaml",
            "xyz_config": "configs/evaluation/feature_matching/xyz/config.yaml",
        }
    }
    first = fingerprints(config)
    settings = yaml.safe_load(orb.read_text())
    settings["sequence"] = "V1_01_easy"
    settings["dataset_root"] = "two"
    orb.write_text(yaml.safe_dump(settings))
    assert fingerprints(config) == first
    settings["sample_hz"] = 4
    orb.write_text(yaml.safe_dump(settings))
    assert fingerprints(config) != first


def test_visually_hard_negative_requires_two_reviews_even_at_distant_poses():
    records = reference({30: "unknown"})
    records[30, 0]["pose_review_aid"]["camera_position_distance_m"] = 100
    first = {**review(30, "non_loop", "a"), "hard_negative": True}
    resolved, _ = consensus(records, [first], policy())
    assert resolved[30, 0]["label"] == "unknown"
    resolved, _ = consensus(records, [first, review(30, "non_loop", "b")], policy())
    assert resolved[30, 0]["label"] == "non_loop"
