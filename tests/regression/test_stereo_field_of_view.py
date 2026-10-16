"""Rectification must not silently discard valid original observations."""

import cv2
import numpy as np

from loop_eval.tasks.feature_matching.xyz.dense_stereo import DenseStereo, correspondences
from loop_eval.tasks.feature_matching.xyz.rectification import (
    cropped_rectification,
    full_field_rectification,
)


def calibration():
    k = np.array([[458.654, 0, 367.215], [0, 457.296, 248.375], [0, 0, 1.0]])
    distortion = np.array([-0.28340811, 0.07395907, 0.00019359, 0.0000176187114])
    relative = np.eye(4)
    relative[0, 3] = -0.11
    return k, distortion, relative


def test_original_border_observations_remain_inside_rectified_canvas():
    k, d, relative = calibration()
    layout = full_field_rectification(k, d, k, d, (752, 480), relative)
    points = np.array([[20.0, 20.0], [732.0, 460.0], [375.0, 239.0]])
    rectified = cv2.undistortPoints(points[:, None], k, d, R=layout.r0, P=layout.p0)[:, 0]
    assert np.all(rectified >= 1)
    assert np.all(rectified < np.asarray(layout.size) - 2)
    assert layout.size[0] > 752
    assert layout.size[1] > 480


def test_canvas_expansion_preserves_focal_length_and_epipolar_geometry():
    k, d, relative = calibration()
    layout = full_field_rectification(k, d, k, d, (752, 480), relative)
    _, _, p0, p1, *_ = cv2.stereoRectify(
        k,
        d,
        k,
        d,
        (752, 480),
        np.ascontiguousarray(relative[:3, :3]),
        np.ascontiguousarray(relative[:3, 3].reshape(3, 1)),
        flags=cv2.CALIB_ZERO_DISPARITY,
        alpha=0,
    )
    assert layout.p0[0, 0] == p0[0, 0]
    assert layout.p1[0, 3] == p1[0, 3]
    assert layout.p0[1, 2] == layout.p1[1, 2]
    point = np.array([[0.3, -0.2, 4.0]])
    raw0 = cv2.projectPoints(point, np.zeros(3), np.zeros(3), k, d)[0]
    raw1 = cv2.projectPoints(point + relative[:3, 3], np.zeros(3), np.zeros(3), k, d)[0]
    a = cv2.undistortPoints(raw0, k, d, R=layout.r0, P=layout.p0)[0, 0]
    b = cv2.undistortPoints(raw1, k, d, R=layout.r1, P=layout.p1)[0, 0]
    np.testing.assert_allclose(a[1], b[1], atol=1e-5)
    np.testing.assert_allclose(a[0] - b[0], -layout.p1[0, 3] / 4, atol=1e-5)


def test_invalid_remap_padding_is_not_real_image_content():
    k, d, relative = calibration()
    layout = full_field_rectification(k, d, k, d, (752, 480), relative)
    assert layout.valid0.dtype == np.bool_
    assert layout.valid0.shape == layout.size[::-1]
    assert not layout.valid0.all()
    raw = np.array([[[20.0, 20.0]]])
    point = cv2.undistortPoints(raw, k, d, R=layout.r0, P=layout.p0)[0, 0]
    assert layout.valid0[int(round(point[1])), int(round(point[0]))]


def make_dense_stub(tmp_path):
    k, d, relative = calibration()
    dense = DenseStereo.__new__(DenseStereo)
    dense.rectification = cropped_rectification(k, d, k, d, (752, 480), relative)
    dense.recovery_rectification = full_field_rectification(k, d, k, d, (752, 480), relative)
    dense.output, dense.signature, dense.recovery_signature = tmp_path, "primary", "expanded"
    dense.k0, dense.d0, dense.raw_size = k, d, (752, 480)
    dense.policy, dense.runtime = {"stereo_lr_max_error_px": 1.0}, {"fixture": True}
    return dense


def test_recovery_restores_cropped_observation_without_replacing_primary(tmp_path):
    dense = make_dense_stub(tmp_path)
    calls = []

    def disparity(stamp, left, right, layout, directory, signature, recovery=False):
        calls.append(recovery)
        value = 12.0 if not recovery else 13.0
        data = np.full(layout.size[::-1], value, np.float32)
        return data, data.copy(), {"disparity_file": str(directory / "1.npz")}

    dense._disparity = disparity
    points = np.array([[375.0, 239.0], [50.0, 30.0]])
    original, old_valid, old_reasons = dense._sample_layout(
        points,
        dense.rectification,
        (np.full((480, 752), 12.0, np.float32),) * 2,
    )
    assert old_valid.tolist() == [True, False]
    assert old_reasons[1] == "rectified_observation_outside_canvas"
    result, valid, reasons, evidence = dense.match(1, "left", "right", points)
    assert valid.all(), reasons
    np.testing.assert_array_equal(result[0], original[0])
    assert evidence["recovered_feature_ids"] == [1]
    assert calls == [False, True]


def test_recovery_does_not_override_inconsistent_primary_disparity(tmp_path):
    dense = make_dense_stub(tmp_path)
    calls = []

    def disparity(stamp, left, right, layout, directory, signature, recovery=False):
        calls.append(recovery)
        return (
            np.full(layout.size[::-1], 12.0, np.float32),
            np.full(layout.size[::-1], 16.0, np.float32),
            {},
        )

    dense._disparity = disparity
    _, valid, reasons, evidence = dense.match(1, "left", "right", [[375.0, 239.0]])
    assert not valid[0]
    assert reasons == ["stereo_left_right_inconsistent"]
    assert evidence["recovered_feature_ids"] == []
    assert calls == [False]


def test_padding_prediction_cannot_become_stereo_evidence():
    h, w = 60, 100
    yy, xx = np.indices((h, w), dtype=np.float32)
    disparity = np.full((h, w), 8.5, np.float32)
    k = np.array([[100, 0, 50], [0, 100, 30], [0, 0, 1.0]], float)
    _, valid, reasons = correspondences(
        [[40, 25]],
        disparity,
        disparity,
        k,
        np.zeros(4),
        np.eye(3),
        np.column_stack((k, np.zeros(3))),
        (xx, yy),
        1.0,
        np.ones((h, w), bool),
        np.zeros((h, w), bool),
        (w, h),
    )
    assert not valid[0]
    assert reasons == ["stereo_correspondence_outside_sensor_content"]
