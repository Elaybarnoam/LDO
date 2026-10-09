"""Known-pose/outlier tests and the operational/offline information boundary."""

import ast
from pathlib import Path

import cv2
import numpy as np
import pytest
from tasks.loop_closure.loop_metrics import query_outcomes, summarize_connections
from tasks.loop_closure.pose_assessment import assess_pose

from loop_verification.configuration import load_policy
from loop_verification.contracts import VerificationInput
from loop_verification.verifier import LoopVerifier


def observations(outliers=0, distortion=True):
    rng = np.random.default_rng(4)
    xyz = rng.uniform([-1.5, -1, 3], [1.5, 1, 8], (100, 3))
    k = np.array([[450.0, 0, 375], [0, 455, 240], [0, 0, 1.0]])
    d = np.array([-0.08, 0.01, 0.001, -0.001]) if distortion else np.zeros(4)
    r, t = np.array([0.015, -0.06, 0.025]), np.array([0.25, -0.04, 0.12])
    pixels = cv2.projectPoints(xyz, r, t, k, d)[0][:, 0]
    pixels += rng.normal(0, 0.15, pixels.shape)
    pixels[:outliers] = rng.uniform([0, 0], [751, 479], (outliers, 2))
    data = VerificationInput(
        30,
        0,
        np.column_stack([np.arange(100)] * 2).astype(np.int64),
        xyz,
        pixels,
        np.ones(100, bool),
        k,
        d,
        (752, 480),
    )
    pose = np.eye(4)
    pose[:3, :3], pose[:3, 3] = cv2.Rodrigues(r)[0], t
    return data, pose


def test_metric_pose_direction_distortion_and_outlier_rejection():
    data, expected = observations(30)
    result = LoopVerifier(load_policy(Path("loop_verification/config.yaml"))).verify(data)
    assert result.status == "accepted", result.to_dict()
    np.testing.assert_allclose(
        result.transform_historical_from_query[:3, 3], expected[:3, 3], atol=0.02
    )
    error = assess_pose(
        result.transform_historical_from_query,
        expected,
        {"maximum_translation_error_m": 0.02, "maximum_rotation_error_degrees": 0.5},
    )
    assert error["within_tolerance"]
    assert len(result.inlier_assignment_ids) >= 65
    assert sum(q < 30 for q, h in result.inlier_assignment_ids) < 3
    assert not result.transform_historical_from_query.flags.writeable


def test_same_observations_have_identical_results():
    data, _ = observations(20)
    verifier = LoopVerifier(load_policy(Path("loop_verification/config.yaml")))
    assert verifier.verify(data).to_dict() == verifier.verify(data).to_dict()


def test_missing_depth_is_insufficient_not_rejected():
    data, _ = observations()
    missing = VerificationInput(
        30,
        0,
        data.assignment_ids.copy(),
        np.full((100, 3), np.nan),
        data.historical_pixels.copy(),
        np.zeros(100, bool),
        data.camera_matrix.copy(),
        data.distortion.copy(),
        data.image_size,
    )
    result = LoopVerifier(load_policy(Path("loop_verification/config.yaml"))).verify(missing)
    assert result.status == "insufficient_evidence"
    assert result.transform_historical_from_query is None


def test_collinear_geometry_rejected_and_planar_geometry_allowed():
    data, _ = observations()
    xyz = np.column_stack([np.linspace(-1, 1, 100), np.zeros(100), np.full(100, 5.0)])
    line = VerificationInput(
        30,
        0,
        data.assignment_ids.copy(),
        xyz,
        data.historical_pixels.copy(),
        data.depth_valid.copy(),
        data.camera_matrix.copy(),
        data.distortion.copy(),
        data.image_size,
    )
    result = LoopVerifier(load_policy(Path("loop_verification/config.yaml"))).verify(line)
    assert result.reason == "degenerate_object_geometry"
    xyz = data.query_camera_xyz.copy()
    xyz[:, 2] = 5
    pixels = cv2.projectPoints(
        xyz, np.zeros(3), np.array([0.2, 0.0, 0.1]), data.camera_matrix, data.distortion
    )[0][:, 0]
    plane = VerificationInput(
        30,
        0,
        data.assignment_ids.copy(),
        xyz,
        pixels,
        data.depth_valid.copy(),
        data.camera_matrix.copy(),
        data.distortion.copy(),
        data.image_size,
    )
    assert (
        LoopVerifier(load_policy(Path("loop_verification/config.yaml"))).verify(plane).status
        == "accepted"
    )


def test_invalid_order_duplicate_ids_and_negative_depth():
    data, _ = observations()
    for change in ("time", "duplicate", "depth"):
        args = [
            30,
            0,
            data.assignment_ids.copy(),
            data.query_camera_xyz.copy(),
            data.historical_pixels.copy(),
            data.depth_valid.copy(),
            data.camera_matrix.copy(),
            data.distortion.copy(),
            data.image_size,
        ]
        if change == "time":
            args[1] = 30
        elif change == "duplicate":
            args[2][1] = args[2][0]
        else:
            args[3][0, 2] = -1
        with pytest.raises(ValueError):
            VerificationInput(*args)


def test_runtime_cannot_import_evaluation_or_read_reference_inputs():
    for root in (Path("loop_verification"), Path("stereo_observations")):
        for path in root.glob("*.py"):
            text = path.read_text()
            assert "state_groundtruth" not in text and "CameraPoses" not in text
            tree = ast.parse(text)
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    assert not (node.module or "").startswith(("tasks.", "modules.", "evaluation."))


def test_pose_accuracy_does_not_make_unknown_label_correct():
    records = [
        {
            "verification": {"status": "accepted", "reason": "passed"},
            "reference_label": "unknown",
            "pose_assessment": {
                "available": True,
                "within_tolerance": True,
                "translation_error_m": 0.0,
                "rotation_error_degrees": 0.0,
            },
        }
    ]
    result = summarize_connections(records)
    assert result["unresolved_accepted"] == 1 and result["correct_accepted"] == 0
    assert result["precision"] is None


def test_known_loop_miss_and_unknown_recall_boundary():
    ref = {(30, 0): {"label": "loop"}, (30, 1): {"label": "loop"}}
    row = {
        "query_timestamp_ns": 30,
        "historical_timestamp_ns": 0,
        "rank": 1,
        "verification": {"status": "accepted"},
        "pose_assessment": {"within_tolerance": True},
    }
    result = query_outcomes(ref, [row], [30], 1)
    assert result["pair_recall"] == 0.5
    assert result["per_query"][0]["miss_reasons"] == {"not_retrieved": 1}
    ref[30, 1]["label"] = "unknown"
    assert query_outcomes(ref, [row], [30], 1)["pair_recall"] is None


def test_shared_stereo_numerical_reconstruction_and_worker_are_preserved():
    import hashlib

    old = Path("evaluation/src/tasks/feature_matching/xyz")
    shared = Path("stereo_observations")
    assert (
        hashlib.sha256((old / "stereo_worker.py").read_bytes()).digest()
        == hashlib.sha256((shared / "stereo_worker.py").read_bytes()).digest()
    )

    def functions(path):
        return {
            node.name: ast.dump(node)
            for node in ast.parse(path.read_text()).body
            if isinstance(node, ast.FunctionDef)
            and node.name in {"project", "triangulate", "reconstruct"}
        }

    assert functions(old / "stereo.py") == functions(shared / "geometry.py")
