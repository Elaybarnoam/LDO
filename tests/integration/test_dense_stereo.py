"""Dense disparity correspondence, occlusion and raw calibration frame tests."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from loop_eval.tasks.feature_matching.xyz.dense_stereo import DenseStereo, correspondences
from loop_eval.tasks.feature_matching.xyz.rectification import Rectification
from loop_eval.tasks.feature_matching.xyz.stereo import project


class DenseStereoTests(unittest.TestCase):
    def test_verified_cache_copy_and_corrupt_source_rejection(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "source"
            target = root / "target"
            source.mkdir()
            target.mkdir()
            left, right = root / "left.png", root / "right.png"
            left.write_bytes(b"left-image")
            right.write_bytes(b"right-image")
            h, w = 60, 100
            yy, xx = np.indices((h, w), dtype=np.float32)
            disparity = np.full((h, w), 8.5, np.float32)
            np.savez_compressed(source / "1.npz", left=disparity, right=disparity)
            saved = {
                "inputs": {
                    "signature": "old",
                    "left_sha256": hashlib.sha256(left.read_bytes()).hexdigest(),
                    "right_sha256": hashlib.sha256(right.read_bytes()).hexdigest(),
                },
                "disparity_sha256": hashlib.sha256((source / "1.npz").read_bytes()).hexdigest(),
                "runtime": {"test": True},
            }
            (source / "1.json").write_text(json.dumps(saved))
            dense = DenseStereo.__new__(DenseStereo)
            dense.output, dense.cache_source = target, source
            dense.signature, dense.source_signature = "new", "old"
            dense.k0 = np.array([[100, 0, 50], [0, 100, 30], [0, 0, 1]], float)
            dense.d0 = np.zeros(4)
            dense.r0 = np.eye(3)
            dense.p0 = np.column_stack((dense.k0, np.zeros(3)))
            dense.maps = [(xx, yy), (xx, yy)]
            dense.rectification = Rectification(
                dense.r0,
                np.eye(3),
                dense.p0,
                dense.p0,
                (w, h),
                (xx, yy),
                (xx, yy),
                np.ones((h, w), bool),
                np.ones((h, w), bool),
            )
            dense.raw_size = (w, h)
            dense.policy = {"stereo_lr_max_error_px": 1.0}
            _, valid, _, metadata = dense.match(1, left, right, [[40, 25]])
            self.assertTrue(valid[0])
            self.assertEqual(metadata["reused_from"], str(source / "1.npz"))
            self.assertEqual((target / "1.npz").read_bytes(), (source / "1.npz").read_bytes())
            (source / "2.npz").write_bytes(b"corrupt")
            (source / "2.json").write_text(json.dumps(saved))
            with self.assertRaisesRegex(ValueError, "integrity validation"):
                dense.match(2, left, right, [[40, 25]])
            self.assertFalse((target / "2.npz").exists())

    def test_subpixel_disparity_and_left_right_consistency(self):
        h, w = 60, 100
        yy, xx = np.indices((h, w), dtype=np.float32)
        disparity = np.full((h, w), 8.5, np.float32)
        k = np.array([[100, 0, 50], [0, 100, 30], [0, 0, 1]], float)
        points = np.array([[40.25, 25.5], [3, 20]], float)
        right, valid, reasons = correspondences(
            points,
            disparity,
            disparity,
            k,
            np.zeros(4),
            np.eye(3),
            np.column_stack((k, np.zeros(3))),
            (xx, yy),
            1.0,
        )
        self.assertTrue(valid[0])
        np.testing.assert_allclose(right[0], [31.75, 25.5], atol=0.04)
        self.assertFalse(valid[1])
        self.assertEqual(reasons[1], "stereo_occluded_or_outside_image")
        _, valid, reasons = correspondences(
            points[:1],
            disparity,
            disparity + 2,
            k,
            np.zeros(4),
            np.eye(3),
            np.column_stack((k, np.zeros(3))),
            (xx, yy),
            1.0,
        )
        self.assertFalse(valid[0])
        self.assertEqual(reasons[0], "stereo_left_right_inconsistent")

    def test_rectified_right_points_map_back_to_original_distorted_camera(self):
        size = (320, 240)
        k = np.array([[250, 0, 160], [0, 250, 120], [0, 0, 1]], float)
        d = np.array([-0.15, 0.02, 0.001, -0.001])
        rotation, _ = cv2.Rodrigues(np.array([0.01, -0.02, 0.005]))
        translation = np.array([-0.12, 0, 0])
        r0, r1, p0, p1, _, _, _ = cv2.stereoRectify(
            k,
            d,
            k,
            d,
            size,
            rotation,
            translation.reshape(3, 1),
            flags=cv2.CALIB_ZERO_DISPARITY,
            alpha=0,
        )
        maps = cv2.initUndistortRectifyMap(k, d, r1, p1, size, cv2.CV_32FC1)
        rect_xyz = np.array([[-0.3, -0.2, 3], [0.2, 0.1, 3], [0, 0, 3]], float)
        raw_xyz = rect_xyz @ r0
        left = project(raw_xyz, k, d)
        expected = project(raw_xyz @ rotation.T + translation, k, d)
        disparity = np.full(size[::-1], -p1[0, 3] / 3, np.float32)
        right, valid, reasons = correspondences(left, disparity, disparity, k, d, r0, p0, maps, 1.0)
        self.assertTrue(valid.all(), reasons)
        np.testing.assert_allclose(right, expected, atol=0.06)


if __name__ == "__main__":
    unittest.main()
