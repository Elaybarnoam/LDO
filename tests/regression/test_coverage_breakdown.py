"""Abstentions must be visible and reconciled in the report pipeline."""

import pytest

from loop_eval.tasks.feature_matching.xyz.coverage import (
    empty_breakdown,
    merge_breakdown,
    summarize_coverage,
    validate_breakdown,
)


def test_joint_reasons_count_each_match_once_and_keep_both_sides():
    features = [
        {"verdict": "supported", "reason": "world_xyz_agrees"},
        {
            "verdict": "untestable",
            "reason": "reliable_stereo_depth_unavailable",
            "query_depth_reason": "low_stereo_parallax",
            "historical_depth_reason": "uncertain_stereo_depth",
        },
        {
            "verdict": "untestable",
            "reason": "reliable_stereo_depth_unavailable",
            "query_depth_reason": "stereo_left_right_inconsistent",
        },
    ]
    breakdown = summarize_coverage(features)
    validate_breakdown(breakdown, 3, 2)
    assert breakdown["depth_failure_pair_counts"] == {
        "low_stereo_parallax / uncertain_stereo_depth": 1,
        "stereo_left_right_inconsistent / reliable": 1,
    }
    assert breakdown["depth_missing_side_counts"] == {"both": 1, "query_only": 1}
    merged = empty_breakdown()
    merge_breakdown(merged, breakdown)
    merge_breakdown(merged, breakdown)
    validate_breakdown(merged, 6, 4)


def test_malformed_or_incomplete_ipc_counts_are_rejected():
    breakdown = empty_breakdown()
    breakdown["untestable_reason_counts"] = {"bad": -1}
    with pytest.raises(ValueError, match="counts"):
        merge_breakdown(empty_breakdown(), breakdown)
    with pytest.raises(ValueError, match="account"):
        validate_breakdown(empty_breakdown(), 2, 1)


def test_domain_counts_retain_peripheral_matches_in_total_denominator():
    data = [
        {
            "verdict": "supported",
            "reason": "world_xyz_agrees",
            "query_primary_rectified_domain": True,
            "historical_primary_rectified_domain": True,
        },
        {
            "verdict": "untestable",
            "reason": "reliable_stereo_depth_unavailable",
            "query_depth_reason": "low_stereo_parallax",
            "query_primary_rectified_domain": False,
            "historical_primary_rectified_domain": True,
        },
    ]
    result = summarize_coverage(data)
    validate_breakdown(result, 2, 1)
    assert result["domain_verdict_counts"] == {
        "primary_overlap_supported": 1,
        "additional_field_untestable": 1,
    }


def test_report_displays_abstention_reasons_without_claiming_negatives():
    from loop_eval.infrastructure.evaluation_file_handler.markdown_report import _feature_review

    review = {
        "status": "complete",
        "checked_pairs": 1,
        "feature_totals": {"supported": 0, "contradicted": 0, "untestable": 1},
        "provenance": {"policy": {"stereo_world_mahalanobis_squared_maximum": 11.345}},
        "coverage_breakdown": summarize_coverage(
            [
                {
                    "verdict": "untestable",
                    "reason": "reliable_stereo_depth_unavailable",
                    "query_depth_reason": "low_stereo_parallax",
                }
            ]
        ),
    }
    text = "\n".join(_feature_review(review))
    assert "low_stereo_parallax / reliable | 1 | 100.00%" in text
    assert "abstentions, not incorrect matches" in text


def test_viewer_explains_uncertainty_gate_and_saved_recovery_source():
    from loop_eval.tasks.feature_matching.viewer.depth_explanation import stereo_details
    from loop_eval.tasks.feature_matching.xyz.evaluator import load_policy

    policy = load_policy("configs/evaluation/feature_matching/xyz/config.yaml")
    point = {"query_feature_id": 7, "query_depth_reason": "uncertain_stereo_depth"}
    pair = {"stereo": {"frames": {"query": {"matching": {"recovered_feature_ids": [7]}}}}}
    details = stereo_details(point, pair, "query", policy)
    assert "Depth sigma / depth > 25%" in details
    assert "Source: Full-field recovery" in details
    assert "Unknown is not a mismatch" in details


def test_coverage_analysis_counts_reused_observation_once_and_checks_integrity(tmp_path):
    import json

    from loop_eval.tasks.feature_matching.xyz.coverage_analysis import analyze_checks

    feature = {
        "verdict": "untestable",
        "reason": "reliable_stereo_depth_unavailable",
        "query_timestamp_ns": 20,
        "historical_timestamp_ns": 10,
        "query_feature_id": 1,
        "historical_feature_id": 2,
        "query_depth_reason": "low_stereo_parallax",
        "historical_depth_reason": None,
    }
    pairs = [
        {
            "query_timestamp_ns": 20,
            "historical_timestamp_ns": 10,
            "stereo": {"feature_results": [feature]},
        },
        {
            "query_timestamp_ns": 30,
            "historical_timestamp_ns": 10,
            "stereo": {"feature_results": [{**feature, "query_timestamp_ns": 30}]},
        },
    ]
    (tmp_path / "pairs.jsonl").write_text("".join(json.dumps(p) + "\n" for p in pairs))
    (tmp_path / "summary.json").write_text(
        json.dumps(
            {
                "complete": True,
                "checked_pairs": 2,
                "feature_totals": {"supported": 0, "contradicted": 0, "untestable": 2},
            }
        )
    )
    result = analyze_checks(tmp_path)
    assert result["unique_frame_feature_observations"] == 3
    assert result["untestable_reason_incidence"] == {"low_stereo_parallax": 2}
    pairs[1]["stereo"]["feature_results"][0]["historical_depth_reason"] = "low_stereo_parallax"
    (tmp_path / "pairs.jsonl").write_text("".join(json.dumps(p) + "\n" for p in pairs))
    with pytest.raises(ValueError, match="inconsistent depth evidence"):
        analyze_checks(tmp_path)
