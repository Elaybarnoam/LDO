"""Pure observation checks and navigation across candidate image boundaries."""

import unittest
from pathlib import Path

import numpy as np

from loop_eval.tasks.feature_matching.viewer.viewer import PairViewer
from loop_eval.tasks.feature_matching.xyz.evaluator import load_policy
from loop_eval.tasks.feature_matching.xyz.xyz import FeatureObservation, check_correspondence

POLICY = load_policy(
    Path(__file__).resolve().parents[2] / "configs/evaluation/feature_matching/xyz/config.yaml"
)


class FeatureXYZTests(unittest.TestCase):
    def observations(self):
        pose = np.eye(4)
        history = pose.copy()
        history[0, 3] = 0.4
        return FeatureObservation(
            2, 7, [20, 30], [0, 0, 4], np.eye(3) * 0.0001, pose
        ), FeatureObservation(1, 8, [40, 50], [-0.4, 0, 4], np.eye(3) * 0.0001, history)

    def test_same_world_point_under_different_camera_poses(self):
        q, h = self.observations()
        r = check_correspondence(q, h, POLICY)
        self.assertEqual(r["verdict"], "supported")
        np.testing.assert_allclose(r["query_world_xyz"], r["historical_world_xyz"])
        self.assertAlmostEqual(r["mahalanobis_squared"], 0)

    def test_wrong_point_and_missing_depth_are_distinct(self):
        q, h = self.observations()
        wrong = FeatureObservation(
            h.timestamp_ns, h.feature_id, h.pixel_xy, [2, 0, 4], h.covariance, h.camera_pose
        )
        self.assertEqual(check_correspondence(q, wrong, POLICY)["verdict"], "contradicted")
        missing = FeatureObservation(
            h.timestamp_ns,
            h.feature_id,
            h.pixel_xy,
            camera_pose=h.camera_pose,
            depth_reason="stereo_left_right_inconsistent",
        )
        r = check_correspondence(q, missing, POLICY)
        self.assertEqual(r["verdict"], "untestable")
        self.assertEqual(r["historical_depth_reason"], "stereo_left_right_inconsistent")
        self.assertEqual(r["query_camera_xyz"], [0, 0, 4])

    def test_invalid_uncertainty_is_not_a_contradiction(self):
        q, h = self.observations()
        invalid = FeatureObservation(
            h.timestamp_ns, h.feature_id, h.pixel_xy, h.camera_xyz, -np.eye(3), h.camera_pose
        )
        self.assertEqual(check_correspondence(q, invalid, POLICY)["verdict"], "untestable")

    def test_feature_navigation_forward_and_backward_crosses_image_pairs(self):
        class Review:
            pass

        review = Review()
        review.policy = POLICY
        review.all_pairs = [
            {
                "stereo": {
                    "feature_results": [{"verdict": "supported"}, {"verdict": "contradicted"}]
                }
            },
            {"stereo": {"feature_results": []}},
            {"stereo": {"feature_results": [{"verdict": "untestable"}]}},
        ]
        viewer = PairViewer(review)
        self.assertEqual(
            viewer.feature_group_counts,
            {"all": 3, "supported": 1, "contradicted": 1, "untestable": 1},
        )
        viewer.move(1)
        self.assertEqual((viewer.index, viewer.feature), (0, 1))
        viewer.move(1)
        self.assertEqual((viewer.index, viewer.feature), (1, 0))
        viewer.move(-1)
        self.assertEqual((viewer.index, viewer.feature), (0, 1))
        viewer.move(-1)
        viewer.move(-1)
        self.assertEqual((viewer.index, viewer.feature), (0, 0))
        viewer.switch_xyz("contradicted")
        self.assertEqual(len(viewer.visible_landmarks(review.pairs[0])), 1)
        viewer.switch_xyz("untestable")
        self.assertEqual(len(review.pairs), 1)
