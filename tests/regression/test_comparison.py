"""Evaluation validity gates, including misses invisible to detector-only checks."""

import json

import pytest

from loop_eval.tasks.loop_closure.comparison.comparison import summarize_features
from loop_eval.tasks.loop_closure.comparison.metrics import (
    paired_interval,
    read_trace,
    retrieval_metrics,
)
from loop_eval.tasks.loop_closure.comparison.reference import load_reference, sha256, write_json


def labels(values, query=30):
    return {(query, h): {"label": label} for h, label in enumerate(values)}


def trace(history, query=30):
    return {query: [{"historical_timestamp_ns": h, "rank": i} for i, h in enumerate(history, 1)]}


def test_missed_positive_is_in_recall_denominator():
    result = retrieval_metrics(labels(["loop", "loop", "non_loop"]), trace([0, 2]), [30], 2)
    assert result["precision"] == 0.5
    assert result["complete_query_pair_recall"] == 0.5
    assert result["complete_query_success"] == 1


def test_unknown_never_becomes_false_positive_or_recall():
    result = retrieval_metrics(labels(["loop", "unknown", "non_loop"]), trace([0, 1]), [30], 2)
    assert result["false_positive"] == 0
    assert result["precision"] is None
    assert result["precision_lower_bound"] == 0.5
    assert result["precision_upper_bound"] == 1
    assert result["complete_query_pair_recall"] is None
    assert result["complete_query_success"] is None


def test_missing_pose_exclusion_does_not_refill_rank():
    result = retrieval_metrics(labels(["loop"]), trace([99, 0]), [30], 1)
    assert result["excluded_missing_reference"] == 1
    assert result["true_positive"] == 0
    assert result["complete_query_success"] == 0


def test_empty_returns_do_not_invent_precision():
    result = retrieval_metrics(labels(["loop"]), trace([]), [30], 1)
    assert result["precision"] is None
    assert result["complete_query_pair_recall"] == 0


@pytest.mark.parametrize("change", ["future", "duplicate", "rank", "history", "truncated"])
def test_invalid_trace_is_rejected(tmp_path, change):
    rows = [
        {"query_timestamp_ns": 0, "eligible_history_count": 0, "candidates": []},
        {
            "query_timestamp_ns": 20,
            "eligible_history_count": 1,
            "candidates": [{"historical_timestamp_ns": 0, "rank": 1}],
        },
    ]
    if change == "future":
        rows[1]["candidates"][0]["historical_timestamp_ns"] = 20
    elif change == "duplicate":
        rows[1]["candidates"].append({"historical_timestamp_ns": 0, "rank": 2})
    elif change == "rank":
        rows[1]["candidates"][0]["rank"] = 2
    elif change == "history":
        rows[1]["eligible_history_count"] = 0
    else:
        rows.pop()
    path = tmp_path / "trace.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    with pytest.raises(ValueError):
        read_trace(path, [0, 20], 20, 5)


def test_reference_reviews_are_auditable_and_universe_is_immutable(tmp_path):
    pair = {"query_timestamp_ns": 30, "historical_timestamp_ns": 0, "label": "unknown"}
    (tmp_path / "pairs.jsonl").write_text(json.dumps(pair) + "\n")
    write_json(
        tmp_path / "manifest.json",
        {"version": 1, "pair_count": 1, "pairs_sha256": sha256(tmp_path / "pairs.jsonl")},
    )
    review = {**pair, "label": "loop", "reviewer": "reviewer", "reason": "shared physical scene"}
    (tmp_path / "reviews.jsonl").write_text(json.dumps(review) + "\n")
    assert load_reference(tmp_path)[1][30, 0]["label"] == "loop"
    (tmp_path / "pairs.jsonl").write_text(json.dumps({**pair, "label": "non_loop"}) + "\n")
    with pytest.raises(ValueError, match="universe differs"):
        load_reference(tmp_path)


def test_zero_match_pairs_remain_in_supported_per_pair():
    pairs = {
        0: {"counts": {"supported": 10, "contradicted": 0, "untestable": 0}},
        1: {"counts": {"supported": 0, "contradicted": 0, "untestable": 0}},
    }
    result = summarize_features(pairs)
    assert result["mean_supported_per_pair_including_zero"] == 5
    assert result["zero_match_pairs"] == 1


def test_paired_block_bootstrap_reproducible():
    left = {"per_query": [{"query_timestamp_ns": i, "success": 0} for i in range(8)]}
    right = {"per_query": [{"query_timestamp_ns": i, "success": 1} for i in range(8)]}
    result = paired_interval(left, right, 0, 2, 100)
    assert result == paired_interval(left, right, 0, 2, 100)
    assert result["interval_95"] == [1, 1]
    assert not paired_interval(left, right, 0, 8, 100)["available"]


def test_comparison_uses_existing_singleton_report_writer(tmp_path):
    from loop_eval.infrastructure.evaluation_file_handler.handler import EvaluationFileHandler
    from loop_eval.tasks.loop_closure.comparison.cli import publish_report

    config = tmp_path / "config.yaml"
    config.write_text("version: 1\n")
    result = {"sequence": "test", "claim_status": "Reference incomplete", "retrieval": {}}
    path = publish_report(result, tmp_path / "output", config)
    assert json.loads(path.read_text())["comparison_result"] == result
    assert "Reference incomplete" in path.with_suffix(".md").read_text()
    with pytest.raises(RuntimeError, match="No active"):
        EvaluationFileHandler.instance()


def test_controlled_matching_rejects_different_pair_sets(monkeypatch, tmp_path):
    from loop_eval.tasks.loop_closure.comparison import comparison

    protocol = {
        "k_values": [1],
        "exclusion_ns": 20,
        "seed": 0,
        "bootstrap_block_queries": 2,
        "bootstrap_samples": 10,
    }
    manifest = {
        "protocol": protocol,
        "sequence": "test",
        "reference_files": {},
        "queries": [{"timestamp_ns": 30}],
        "images": {"0": {"sha256": "a"}, "30": {"sha256": "b"}},
        "excluded_queries_missing_pose": [],
    }
    monkeypatch.setattr(comparison, "load_reference", lambda root: (manifest, labels(["loop"])))
    monkeypatch.setattr(comparison, "verify_images", lambda *args: None)
    monkeypatch.setattr(comparison, "sha256", lambda path: "hash")
    monkeypatch.setattr(comparison, "read_trace", lambda *args: trace([0]))
    pair = {"counts": {"supported": 1, "contradicted": 0, "untestable": 0}, "images": ["b", "a"]}

    def profile(path):
        return {
            "source_hash": "hash",
            "policy": {"version": 8},
            "provenance": {"input_and_code_sha256": {"/xyz.py": "same"}},
            "pairs": {(30, 0): pair} if path.name == "orb" else {},
        }

    monkeypatch.setattr(comparison, "feature_profile", profile)
    methods = {
        name: {"replay": "replay", "trace": "trace", "checks": name} for name in ("orb", "ldo")
    }
    with pytest.raises(ValueError, match="identical pair sets"):
        comparison.compare(tmp_path, methods, protocol, fixed=True)


def test_suite_does_not_drop_unavailable_sequences(tmp_path):
    from loop_eval.tasks.loop_closure.comparison.suite import aggregate

    protocol = {"k_values": [1]}
    paths = []
    for sequence, precision in (("one", 1.0), ("two", None)):
        metric = {
            "precision": precision,
            "complete_query_pair_recall": None,
            "complete_query_success": None,
        }
        result = {
            "sequence": sequence,
            "protocol": protocol,
            "retrieval": {"1": {"orb": metric, "ldo": metric}},
        }
        path = tmp_path / f"{sequence}.json"
        write_json(path, {"status": "completed", "comparison_result": result})
        paths.append(path)
    result = aggregate(paths)
    precision = result["equal_sequence_metrics"]["1"]["ldo"]["precision"]
    assert precision["equal_sequence_mean"] is None
    assert precision["available_sequences"] == 1
    with pytest.raises(ValueError, match="Duplicate sequence"):
        aggregate([paths[0], paths[0]])


def test_verified_suite_requires_equal_policies_and_preserves_missing_recall(tmp_path):
    from loop_eval.tasks.loop_closure.comparison.suite import aggregate

    paths = []
    reports = []
    for sequence, recall in (("one", 0.8), ("two", None)):
        retrieval = {
            "precision": None,
            "complete_query_pair_recall": None,
            "complete_query_success": None,
        }
        verified = {"pair_recall": recall, "query_success": recall}
        report = {
            "status": "complete",
            "comparison_result": {
                "sequence": sequence,
                "protocol": {"k_values": [1]},
                "retrieval": {"1": {"orb": retrieval, "ldo": retrieval}},
                "verified_connections": {
                    "verifier_policy": {"version": 1},
                    "assessment_policy": {"version": 1},
                    "query_metrics": {"1": {"orb": verified, "ldo": verified}},
                },
            },
        }
        path = tmp_path / f"{sequence}.json"
        write_json(path, report)
        paths.append(path)
        reports.append(report)
    result = aggregate(paths)["verified_equal_sequence_metrics"]["1"]["ldo"]["pair_recall"]
    assert result == {"equal_sequence_mean": None, "available_sequences": 1, "total_sequences": 2}
    reports[1]["comparison_result"]["verified_connections"]["verifier_policy"] = {"version": 2}
    paths[1].write_text(json.dumps(reports[1]), encoding="utf-8")
    with pytest.raises(ValueError, match="policies differ"):
        aggregate(paths)
    del reports[1]["comparison_result"]["verified_connections"]
    paths[1].write_text(json.dumps(reports[1]), encoding="utf-8")
    with pytest.raises(ValueError, match="Cannot mix"):
        aggregate(paths)
