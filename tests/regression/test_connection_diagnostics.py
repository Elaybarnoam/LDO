"""Independent numerical checks and diagnostic evidence semantics."""

import json
from hashlib import sha256

import numpy as np
import pytest
from scipy.linalg import expm
from scipy.spatial.transform import Rotation

from loop_eval.tasks.loop_closure.connection_diagnostics import (
    EVIDENCE_POLICY,
    attach_inlier_xyz,
    classify,
    distribution,
    render_diagnostics,
    risk_curve,
    summarize,
)
from loop_eval.tasks.loop_closure.pose_assessment import assess_pose
from loop_eval.tasks.loop_closure.statistical_geometry import (
    gaussian_consistency,
    pose_consistency,
    pose_residual,
    rigid_transform,
    world_point_consistency,
)

POLICY = {"maximum_translation_error_m": 0.2, "maximum_rotation_error_degrees": 5.0}


def row(t=0.1, a=1.0, counts=None, quality=0.8, status="accepted"):
    return {
        "status": status,
        "pose_assessment": {
            "available": True,
            "translation_error_m": t,
            "rotation_error_degrees": a,
            "within_tolerance": t <= 0.2 and a <= 5,
        },
        "feature_counts": counts or {"supported": 20, "contradicted": 0, "untestable": 0},
        "verification_diagnostics": {"inlier_ratio": quality},
        "evidence_group": "example",
    }


def test_world_covariance_includes_cross_correlation():
    joint = np.block([[np.eye(3), 0.5 * np.eye(3)], [0.5 * np.eye(3), np.eye(3)]])
    result = world_point_consistency([1, 0, 0], [0, 0, 0], joint, calibrated=True)
    assert result["statistical_consistency"]["mahalanobis_squared"] == pytest.approx(1)
    assert result["statistical_consistency"]["compatible"]
    independent = world_point_consistency([1, 0, 0], [0, 0, 0], np.eye(6), calibrated=True)
    assert independent["statistical_consistency"]["mahalanobis_squared"] == pytest.approx(0.5)


def test_uncalibrated_or_missing_covariance_never_supplies_verdict():
    for covariance in (None, np.eye(3)):
        result = gaussian_consistency([1, 0, 0], covariance)
        assert not result["available"]
        assert "compatible" not in result
        assert "tail_probability" not in result


@pytest.mark.parametrize(
    "covariance",
    [
        np.zeros((3, 3)),
        -np.eye(3),
        np.eye(2),
        [[1, 1, 0], [0, 1, 0], [0, 0, 1]],
        np.full((3, 3), np.nan),
    ],
)
def test_invalid_covariance_rejected(covariance):
    with pytest.raises(ValueError):
        gaussian_consistency([0, 0, 0], covariance, calibrated=True)


@pytest.mark.parametrize("angle", [0.0, 1e-7, 0.5, np.pi - 1e-8])
def test_se3_log_recovers_known_exponential(angle):
    phi = np.array([0, 0, angle])
    rho = np.array([0.3, -0.4, 0.7])
    algebra = np.zeros((4, 4))
    algebra[:3, :3] = [[0, -angle, 0], [angle, 0, 0], [0, 0, 0]]
    algebra[:3, 3] = rho
    reference = np.eye(4)
    reference[:3, :3] = Rotation.from_euler("x", 0.4).as_matrix()
    reference[:3, 3] = [2, 3, 4]
    estimate = reference @ expm(algebra)
    np.testing.assert_allclose(pose_residual(estimate, reference), np.r_[rho, phi], atol=1e-8)
    result = pose_consistency(estimate, reference, np.eye(6), calibrated=True)
    assert result["statistical_consistency"]["mahalanobis_squared"] == pytest.approx(
        rho @ rho + phi @ phi
    )


def test_relative_camera_transform_direction_and_error_boundary():
    world_history = np.eye(4)
    world_history[:3, :3] = Rotation.from_euler("z", 90, degrees=True).as_matrix()
    world_query = np.eye(4)
    world_query[:3, 3] = [1, 0, 0]
    reference = np.linalg.inv(world_history) @ world_query
    np.testing.assert_allclose(reference @ [0, 0, 0, 1], [0, -1, 0, 1], atol=1e-10)
    estimate = reference.copy()
    estimate[2, 3] += 0.2
    result = assess_pose(estimate, reference, POLICY)
    assert result["within_tolerance"]
    estimate[2, 3] += 1e-6
    assert not assess_pose(estimate, reference, POLICY)["within_tolerance"]


def test_bad_transform_not_repaired():
    bad = np.eye(4)
    bad[0, 0] = 2
    with pytest.raises(ValueError):
        rigid_transform(bad)


def test_supported_pose_failure_is_not_scene_false_positive():
    candidate = row(t=0.3)
    assert classify(candidate, EVIDENCE_POLICY) == "pose_failure_with_dominant_xyz_support"
    candidate["feature_counts"] = {"supported": 0, "contradicted": 20, "untestable": 0}
    assert classify(candidate, EVIDENCE_POLICY) == "pose_failure_with_dominant_xyz_contradiction"
    candidate["feature_counts"] = {"supported": 0, "contradicted": 0, "untestable": 20}
    assert classify(candidate, EVIDENCE_POLICY) == "pose_failure_with_mixed_or_insufficient_xyz"


def test_risk_curve_retains_all_tied_scores_and_omits_unknown_pose_from_summary():
    rows = [row(t=0.1, quality=0.8), row(t=0.3, quality=0.8), row(t=0.5, quality=0.5)]
    curve = risk_curve(rows, "inlier_ratio", True)
    assert [p["retained"] for p in curve["points"]] == [2, 3]
    assert curve["points"][0]["pose_error_rate"] == 0.5
    unknown = row()
    unknown["pose_assessment"] = {"available": False}
    rows += [unknown, row(status="rejected")]
    result = summarize(rows, POLICY)
    assert result["accepted"] == 4
    assert result["pose_unknown"] == 1
    assert result["pose_inconsistent"] == 2
    assert result["pose_error_rate_among_judgeable"] == pytest.approx(2 / 3)
    assert result["failure_gates"] == {"translation_only": 2}


def test_empirical_cdf_and_empty_distribution():
    result = distribution([1, 1, 3, 5])
    assert result["empirical_cdf"] == [[1, 0.5], [3, 0.75], [5, 1.0]]
    assert distribution([])["median"] is None
    assert distribution([1, 1, 3, 5])["median"] == 2


def test_statistical_pose_contract_is_optional_and_explicit():
    result = assess_pose(np.eye(4), np.eye(4), POLICY, residual_covariance=np.eye(6))
    assert not result["pose_statistics"]["statistical_consistency"]["available"]
    calibrated = assess_pose(
        np.eye(4), np.eye(4), POLICY, residual_covariance=np.eye(6), calibrated=True
    )
    assert calibrated["pose_statistics"]["statistical_consistency"]["compatible"]


def test_empty_report_does_not_invent_error_rate():
    task = {"methods": {"orb": summarize([], POLICY)}, "limitations": "Unknown is not false."}
    rendered = "\n".join(render_diagnostics(task))
    assert "Unavailable" in rendered
    assert "not a proven false revisit" in rendered


@pytest.mark.parametrize("bad", [None, "hash", "image", "inlier_id", "count", "duplicate"])
def test_exact_pnp_inlier_feature_join_and_provenance(tmp_path, bad):
    counts = {"supported": 1, "contradicted": 1, "untestable": 1}
    features = [
        {
            "query_feature_id": i,
            "historical_feature_id": i + 10,
            "verdict": verdict,
            "reason": "depth_missing",
        }
        for i, verdict in enumerate(counts)
    ]
    pair = {
        "query_timestamp_ns": 100,
        "historical_timestamp_ns": 50,
        "measurements": {"query_image_sha256": "q", "historical_image_sha256": "h"},
        "stereo": {"feature_results": features},
    }
    record = {
        "query_image_sha256": "q",
        "historical_image_sha256": "h",
        "verification": {"inlier_assignment_ids": [[1, 11], [2, 12]]},
    }
    candidate = {
        "method": "ldo",
        "query_timestamp_ns": 100,
        "historical_timestamp_ns": 50,
        "feature_counts": counts,
        "pose_assessment": {"available": True, "within_tolerance": False},
    }
    if bad == "image":
        record["query_image_sha256"] = "different"
    elif bad == "inlier_id":
        record["verification"]["inlier_assignment_ids"] = [[8, 18]]
    elif bad == "count":
        candidate["feature_counts"] = {"supported": 9, "contradicted": 1, "untestable": 1}
    elif bad == "duplicate":
        pair["stereo"]["feature_results"].append(features[0])
    content = (json.dumps(pair) + "\n").encode()
    (tmp_path / "pairs.jsonl").write_bytes(content)
    expected = {"ldo_xyz": sha256(content).hexdigest() if bad != "hash" else "wrong"}
    config = {"methods": {"ldo": {"checks": str(tmp_path)}}}
    if bad:
        with pytest.raises(ValueError):
            attach_inlier_xyz([candidate], {("ldo", 100, 50): record}, config, expected)
    else:
        attach_inlier_xyz([candidate], {("ldo", 100, 50): record}, config, expected)
        assert candidate["pnp_inlier_xyz_counts"] == {
            "supported": 0,
            "contradicted": 1,
            "untestable": 1,
        }
        assert candidate["pnp_inlier_unknown_reasons"] == {"depth_missing": 1}


def test_world_consistency_is_invariant_to_shared_world_rotation():
    rotation = Rotation.from_euler("xyz", [0.2, -0.5, 0.9]).as_matrix()
    q, h = np.array([1.0, 2, 3]), np.array([0.5, 1, 2])
    joint = np.diag([1.0, 2, 3, 4, 5, 6])
    block = np.zeros((6, 6))
    block[:3, :3] = block[3:, 3:] = rotation
    original = world_point_consistency(q, h, joint, calibrated=True)
    transformed = world_point_consistency(
        rotation @ q, rotation @ h, block @ joint @ block.T, calibrated=True
    )
    assert original["statistical_consistency"]["mahalanobis_squared"] == pytest.approx(
        transformed["statistical_consistency"]["mahalanobis_squared"]
    )
