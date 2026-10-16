"""Independent synthetic geometry invariants for the simulator reference oracle."""

from pathlib import Path

import cv2
import numpy as np
import pytest
import yaml

from loop_eval.tasks.reference_geometry.geometry import (
    CV_TO_NED,
    backproject,
    camera_pose,
    check_features,
    decode_depth,
    overlap,
    sample_depth,
    visibility,
)

POLICY = yaml.safe_load(
    (
        Path(__file__).resolve().parents[2] / "configs/evaluation/reference_geometry/config.yaml"
    ).read_text()
)["protocol"]


def test_packed_depth_preserves_float_bytes(tmp_path):
    expected = np.full((640, 640), 3.125, np.float32)
    path = tmp_path / "depth.png"
    assert cv2.imwrite(str(path), expected.view(np.uint8).reshape(640, 640, 4))
    np.testing.assert_array_equal(decode_depth(path), expected)


def test_pose_is_camera_to_world_with_correct_axes():
    t = camera_pose([1, 2, 3, 0, 0, 0, 1])
    np.testing.assert_allclose(t[:3, :3], CV_TO_NED)
    np.testing.assert_allclose(t @ [0, 0, 4, 1], [5, 2, 3, 1])
    with pytest.raises(ValueError):
        camera_pose([0, 0, 0, 0, 0, 0, 0])


def test_identical_views_and_nonoverlap():
    d = np.full((640, 640), 4.0, np.float32)
    row = overlap(d, d, np.eye(4), POLICY)
    assert row["label"] == "loop"
    assert row["symmetric_overlap"] == 1
    t = np.eye(4)
    t[0, 3] = 20
    assert overlap(d, d, t, POLICY)["label"] == "non_loop"
    unknown = np.zeros_like(d)
    assert overlap(unknown, d, np.eye(4), POLICY)["label"] == "unknown"


def test_occlusion_and_actual_stereo_disparity():
    d = np.full((640, 640), 4.0, np.float32)
    pixels = np.array([[320.0, 320.0]])
    points = backproject(pixels, [4])
    t = np.eye(4)
    t[0, 3] = -0.25
    projected, visible = visibility(points, d, t, POLICY)
    np.testing.assert_allclose(projected, [[300.0, 320.0]])
    assert visible[0]
    _, occluded = visibility(points, d / 2, np.eye(4), POLICY)
    assert not occluded[0]


def test_feature_checks_do_not_turn_bad_geometry_into_unknown():
    d = np.full((640, 640), 4.0, np.float32)
    q = np.array([[320.0, 320.0], [100.0, 100.0]])
    h = np.array([[320.0, 320.0], [400.0, 400.0]])
    result = check_features(q, h, d, d, np.eye(4), POLICY)
    assert result["counts"] == {"supported": 1, "contradicted": 1, "untestable": 0}
    t = np.eye(4)
    t[2, 3] = -10
    assert check_features(q, h, d, d, t, POLICY)["counts"]["contradicted"] == 2


def test_depth_edges_and_borders_are_unknown_not_false():
    d = np.full((640, 640), 4.0, np.float32)
    d[320, 321] = 8
    points = np.array([[320.0, 320.0], [0.0, 0.0], [200.0, 200.0]])
    _, valid = sample_depth(d, points, POLICY)
    assert valid.tolist() == [False, False, True]
    result = check_features(points, points, d, d, np.eye(4), POLICY)
    assert result["counts"] == {"supported": 1, "contradicted": 0, "untestable": 2}


def test_reference_feature_correct_under_stereo_transform():
    d = np.full((640, 640), 4.0, np.float32)
    t = np.eye(4)
    t[0, 3] = -0.25
    result = check_features([[320.0, 320.0]], [[300.0, 320.0]], d, d, t, POLICY)
    assert result["counts"]["supported"] == 1


def test_overlap_bounds_resolve_partial_depth_without_false_negative():
    d = np.full((640, 640), 4.0, np.float32)
    partial = d.copy()
    partial[:100] = 0
    row = overlap(partial, d, np.eye(4), POLICY)
    assert row["label"] == "loop"
    lo, hi = row["symmetric_overlap_bounds"]
    assert 0.2 < lo < hi <= 1
    t = np.eye(4)
    t[0, 3] = 20
    row = overlap(partial, d, t, POLICY)
    assert row["label"] == "non_loop"
    assert row["symmetric_overlap_bounds"][1] < 0.2


def test_config_rejects_unpinned_and_unsafe_paths():
    from copy import deepcopy

    from loop_eval.tasks.reference_geometry.cli import validate_config

    config = yaml.safe_load(
        (
            Path(__file__).resolve().parents[2]
            / "configs/evaluation/reference_geometry/config.yaml"
        ).read_text()
    )
    validate_config(config)
    bad = deepcopy(config)
    bad["dataset"]["environment"] = "../elsewhere"
    with pytest.raises(ValueError):
        validate_config(bad)
    bad = deepcopy(config)
    bad["protocol"]["frame_stride"] = 0
    with pytest.raises(ValueError):
        validate_config(bad)


def test_depth_coverage_explains_each_frozen_gate():
    from loop_eval.tasks.reference_geometry.depth_coverage import reasons

    d = np.full((640, 640), 4.0, np.float32)
    d[100, 100] = np.nan
    d[200, 200] = 100
    d[300, 301] = 10
    points = [[0, 0], [100, 100], [200, 200], [300, 300], [400, 400]]
    assert reasons(d, points, POLICY).tolist() == [
        "outside_image_or_nonfinite_pixel",
        "nonfinite_depth",
        "depth_out_of_range",
        "depth_boundary",
        "usable",
    ]


def test_report_keeps_revisit_and_pose_errors_separate():
    from loop_eval.tasks.loop_closure.comparison.comparison import render_comparison
    from loop_eval.tasks.reference_geometry.reporting import aggregate, render

    metrics = {
        "true_positive_pairs": 1,
        "false_positive_pairs": 2,
        "unknown_pairs": 1,
        "returned_pairs": 4,
        "confirmed_events": 1,
        "detected_confirmed_events": 1,
        "reference_complete": False,
    }
    connection = {
        "accepted": 2,
        "pose_consistent": 1,
        "independent_reference": {
            "true_positive_pairs": 2,
            "false_positive_pairs": 0,
            "unknown_pairs": 0,
        },
    }
    sequence = {
        "trajectory": "P000",
        "retrieval": {str(k): {name: metrics for name in ("orb", "ldo")} for k in (1, 5)},
        "features": {
            name: {"supported": 3, "contradicted": 1, "untestable": 2} for name in ("orb", "ldo")
        },
        "connections": {name: connection for name in ("orb", "ldo")},
    }
    rows = aggregate([sequence], 5)
    assert rows["orb"]["precision"] is None
    assert rows["orb"]["precision_lower_bound"] == 0.25
    assert rows["orb"]["precision_upper_bound"] == 0.5
    assert rows["orb"]["event_recall"] is None
    assert rows["orb"]["pose_inconsistent"] == 1
    assert rows["orb"]["accepted_reference"]["false_positive_pairs"] == 0
    task = {
        "manifest": {"protocol": {"top_k": 5, "exclusion_ns": 5_000_000_000}},
        "sequences": [sequence],
    }
    text = "\n".join(render(task))
    assert "Precision bounds" in text and "Unavailable" in text
    assert "K=1" in text
    assert "### Accepted constraints" in text
    report = render_comparison(
        {
            "sequence": "pilot",
            "claim_status": "Pilot only",
            "retrieval": {},
            "reference_geometry": task,
        }
    )
    assert "TartanAir V2" in report
