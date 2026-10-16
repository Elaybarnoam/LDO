"""All original ORB correspondences reach feature evaluation without RANSAC."""

import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

from loop_eval.tasks.feature_matching.xyz.evaluator import load_policy
from loop_eval.tasks.feature_matching.xyz.geometry import ImageGeometry


class FeatureHandoffTests(unittest.TestCase):
    def test_every_original_orb_pair_reaches_stereo_without_fundamental_fit(self):
        geometry = ImageGeometry.__new__(ImageGeometry)
        geometry.policy = load_policy(
            Path(__file__).resolve().parents[2]
            / "configs/evaluation/feature_matching/xyz/config.yaml"
        )
        geometry.resolution = (640, 480)
        geometry.k = np.eye(3)
        points = np.array([[20 * i, 30 * i] for i in range(10)], float)
        features = {
            "points": points,
            "undistorted": points,
            "descriptors": np.zeros((10, 32), np.uint8),
            "sha256": "test",
        }
        geometry.features = lambda _: features
        original = [cv2.DMatch(i, 9 - i, float(i)) for i in range(10)]
        geometry.mutual_matches = lambda *_: original
        received = []
        with patch("cv2.findFundamentalMat", side_effect=AssertionError("RANSAC must not run")):
            result = geometry.check("q", "h", None, 0, on_matches=lambda m: received.extend(m))
        self.assertEqual(len(received), 10)
        self.assertTrue(all(a is b for a, b in zip(received, original, strict=True)))
        self.assertEqual(result["measurements"]["match_count"], 10)
        self.assertEqual(result["ransac"]["status"], "disabled_feature_evaluation")
