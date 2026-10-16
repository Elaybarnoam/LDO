"""Calibrated stereo recovery, world-frame comparison and full checker flow."""

import json
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np
import test_candidate_evaluator as fixture_module
import yaml
from scipy.spatial.transform import Rotation

from loop_eval.infrastructure.evaluation_file_handler.handler import EvaluationFileHandler
from loop_eval.tasks.feature_matching.xyz.evaluator import check_trace, load_policy
from loop_eval.tasks.feature_matching.xyz.stereo import (
    classify_stereo,
    compare_landmarks,
    project,
    reconstruct,
)

CONFIG = fixture_module.CONFIG


class StereoEvaluatorTests(unittest.TestCase):
    def test_triangulation_recovers_original_camera_axes_with_distortion_and_rotation(self):
        policy = load_policy(CONFIG)
        k0 = np.array([[450, 0, 370], [0, 445, 245], [0, 0, 1]], float)
        k1 = np.array([[455, 0, 375], [0, 448, 248], [0, 0, 1]], float)
        d0 = np.array([-0.2, 0.05, 0.0002, -0.0001])
        d1 = np.array([-0.25, 0.06, -0.0001, 0.0002])
        relative = np.eye(4)
        relative[:3, :3] = Rotation.from_euler("xyz", [0.01, -0.005, 0.015]).as_matrix()
        relative[:3, 3] = [-0.11, -0.002, 0.001]
        points = np.random.default_rng(7).uniform([-0.5, -0.4, 2], [0.5, 0.4, 5], size=(50, 3))
        lp = project(points, k0, d0)
        rp = project(points @ relative[:3, :3].T + relative[:3, 3], k1, d1)
        recovered, covariance, reliable, reasons = reconstruct(
            lp, rp, k0, d0, k1, d1, relative, policy
        )
        self.assertTrue(reliable.all(), reasons)
        np.testing.assert_allclose(recovered, points, atol=2e-5)
        self.assertTrue((np.linalg.eigvalsh(covariance) >= -1e-10).all())

    def test_negative_depth_low_parallax_and_increasing_depth_uncertainty(self):
        policy = load_policy(CONFIG)
        k = np.array([[400, 0, 320], [0, 400, 240], [0, 0, 1]], float)
        d = np.zeros(4)
        relative = np.eye(4)
        relative[0, 3] = -0.1
        points = np.array([[0, 0, 2], [0, 0, 6], [0, 0, 40]], float)
        lp, rp = project(points, k, d), project(points + relative[:3, 3], k, d)
        xyz, covariance, valid, reasons = reconstruct(lp, rp, k, d, k, d, relative, policy)
        self.assertGreater(covariance[1, 2, 2], covariance[0, 2, 2] * 50)
        self.assertFalse(valid[2])
        self.assertEqual(reasons[2], "low_stereo_parallax")
        _, _, valid, reasons = reconstruct(rp[:1], lp[:1], k, d, k, d, relative, policy)
        self.assertFalse(valid[0])
        self.assertEqual(reasons[0], "nonpositive_depth")

    def test_world_xyz_and_bidirectional_reprojection_under_camera_motion(self):
        policy = load_policy(CONFIG)
        k = np.array([[400, 0, 320], [0, 400, 240], [0, 0, 1]], float)
        distortion = np.zeros(4)
        world = np.random.default_rng(3).uniform([-0.5, -0.4, 3], [0.5, 0.4, 5], size=(40, 3))
        hpose, qpose = np.eye(4), np.eye(4)
        qpose[:3, :3] = Rotation.from_euler("xyz", [0.08, -0.05, 0.15]).as_matrix()
        qpose[:3, 3] = [0.5, 0.1, 0.05]
        qpoints = (world - qpose[:3, 3]) @ qpose[:3, :3]
        hpoints = world.copy()
        qp, hp = project(qpoints, k, distortion), project(hpoints, k, distortion)
        covariance = np.tile(np.eye(3) * 0.00001, (len(world), 1, 1))
        checked = compare_landmarks(
            qpoints, hpoints, covariance, covariance, qpose, hpose, qp, hp, k, distortion, policy
        )
        self.assertTrue(checked["accepted"].all())
        np.testing.assert_allclose(checked["query_world_xyz"], world, atol=1e-12)
        np.testing.assert_allclose(checked["historical_world_xyz"], world, atol=1e-12)
        self.assertLess(checked["cross_reprojection_px"].max(), 1e-10)
        wrong = hpoints + [1.5, 0.7, 0]
        rejected = compare_landmarks(
            qpoints, wrong, covariance, covariance, qpose, hpose, qp, hp, k, distortion, policy
        )
        self.assertFalse(rejected["accepted"].any())

    def test_end_to_end_stereo_support_contradiction_and_missing_right_image(self):
        for contradiction, missing, outcome in (
            (False, False, "overlap_supported"),
            (True, False, "suspicious"),
            (False, True, "inconclusive"),
        ):
            with self.subTest(outcome=outcome), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                replay, trace = fixture_module.CandidateEvaluatorTests().fixture(
                    root, contradiction
                )
                left = root / "mav0/cam0"
                right = root / "mav0/cam1"
                (right / "data").mkdir(parents=True)
                calibration = yaml.safe_load((left / "sensor.yaml").read_text())
                transform = np.eye(4)
                transform[0, 3] = 0.12
                calibration["T_BS"]["data"] = transform.ravel().tolist()
                (right / "sensor.yaml").write_text(yaml.safe_dump(calibration))
                stamps = [0] if missing else [0, 21_000_000_000]
                (right / "data.csv").write_text(
                    "#timestamp,filename\n" + "".join(f"{stamp},{stamp}.png\n" for stamp in stamps)
                )
                for stamp in stamps:
                    image = cv2.imread(str(left / "data" / f"{stamp}.png"), cv2.IMREAD_GRAYSCALE)
                    shifted = np.zeros_like(image)
                    shifted[:, :-8] = image[:, 8:]
                    cv2.imwrite(str(right / "data" / f"{stamp}.png"), shifted)
                    fixture_module.export_fixture_orb(root, right / "data" / f"{stamp}.png")
                fixture_policy = load_policy(CONFIG)
                fixture_policy["stereo_backend"] = "orb_mutual"
                fixture_config = root / "fixture-policy.yaml"
                fixture_config.write_text(yaml.safe_dump(fixture_policy))
                events = []
                handler = EvaluationFileHandler(root / "report.json", {}, ["orb"], queue_capacity=4)
                handler.enqueue(
                    "orb",
                    {
                        "event_type": "retrieval_setup",
                        "payload": {
                            "camera": "cam0",
                            "sample_hz": 2,
                            "temporal_exclusion_seconds": 20,
                            "top_k": 5,
                            "ranking": "score",
                            "imu_usage": "None",
                            "provenance": {"revision": "fixture"},
                            "replay_sha256": "hash",
                        },
                    },
                )
                handler.enqueue(
                    "orb",
                    {
                        "event_type": "retrieval_query",
                        "payload": {
                            "query_timestamp_ns": 21_000_000_000,
                            "eligible_history_count": 1,
                            "feature_count": 1200,
                            "bow_word_count": 50,
                            "timings_ms": {},
                            "candidates": [
                                {"historical_timestamp_ns": 0, "rank": 1, "score": 0.999}
                            ],
                        },
                    },
                )

                def publish(name, payload, stamp=None, events=events, handler=handler):
                    events.append((name, payload))
                    handler.enqueue("orb", {"event_type": name, "payload": payload})

                try:
                    result = check_trace(
                        root, replay, trace, root / "checks", fixture_config, on_event=publish
                    )
                finally:
                    handler.close("complete")
                report = (root / "report.md").read_text()
                self.assertIn("Feature correspondence XYZ evaluation", report)
                self.assertEqual(result["outcome_counts"], {"feature_evaluated": 1})
                counts = result["feature_totals"]
                self.assertEqual(
                    sum(counts.values()),
                    json.loads((root / "checks/pairs.jsonl").read_text())["measurements"][
                        "match_count"
                    ],
                )
                if missing:
                    self.assertEqual(counts["untestable"], sum(counts.values()))
                elif contradiction:
                    self.assertGreater(counts["contradicted"], 0)
                else:
                    self.assertGreater(counts["supported"], 0)
                pair = json.loads((root / "checks/pairs.jsonl").read_text())
                self.assertIsNone(pair["accuracy_label"])
                if not missing:
                    self.assertGreaterEqual(pair["stereo"]["paired_landmarks"], 20)
                    self.assertTrue(pair["stereo"]["landmarks"])
                    self.assertIn("query_world_xyz", pair["stereo"]["landmarks"][0])
                    event = next(payload for name, payload in events if name == "candidate_checked")
                    self.assertNotIn("landmarks", event["stereo"])
                    self.assertEqual(event["landmark_evidence_line"], 1)

    def test_support_requirement_scales_with_all_reported_feature_matches(self):
        policy = load_policy(CONFIG)
        evidence = {
            "available": True,
            "reference_pose_available": True,
            "reported_match_count": 26,
            "paired_landmarks": 11,
            "consistent_landmarks": 11,
            "consistent_coverage": 0.2,
            "paired_coverage": 0.2,
        }
        self.assertEqual(classify_stereo(evidence, policy)[0], "overlap_supported")
        evidence.update(paired_landmarks=10, consistent_landmarks=10)
        self.assertEqual(classify_stereo(evidence, policy)[0], "inconclusive")
        evidence.update(paired_landmarks=2, consistent_landmarks=2)
        self.assertEqual(classify_stereo(evidence, policy)[0], "inconclusive")
        evidence.update(reported_match_count=100, paired_landmarks=20, consistent_landmarks=20)
        self.assertEqual(classify_stereo(evidence, policy)[0], "inconclusive")
        evidence.update(reported_match_count=0, paired_landmarks=0, consistent_landmarks=0)
        self.assertEqual(classify_stereo(evidence, policy)[0], "inconclusive")

    def test_concentrated_matches_can_support_without_grid_coverage(self):
        from loop_eval.tasks.feature_matching.viewer.viewer import xyz_pair_status

        policy = load_policy(CONFIG)
        evidence = {
            "available": True,
            "reference_pose_available": True,
            "reported_match_count": 32,
            "paired_landmarks": 29,
            "consistent_landmarks": 28,
        }
        self.assertNotIn("minimum_image_coverage", policy)
        self.assertEqual(classify_stereo(evidence, policy)[0], "overlap_supported")
        pair = {
            "measurements": {"match_count": 32},
            "stereo": {
                "landmarks": [{"mahalanobis_squared": 0.1} for _ in range(28)]
                + [{"mahalanobis_squared": 20}]
            },
        }
        self.assertEqual(xyz_pair_status(pair, policy, 752, 480), "supported")
        evidence["consistent_landmarks"] = 2
        self.assertEqual(classify_stereo(evidence, policy)[0], "suspicious")
        evidence["paired_landmarks"] = 12
        self.assertEqual(classify_stereo(evidence, policy)[0], "inconclusive")

    def test_insufficient_depth_cannot_inherit_positive_2d_evidence(self):
        policy = load_policy(CONFIG)
        evidence = {
            "available": True,
            "reference_pose_available": True,
            "reported_match_count": 26,
            "paired_landmarks": 5,
            "consistent_landmarks": 5,
            "consistent_ratio": 1.0,
            "consistent_coverage": 0.5,
        }
        self.assertEqual(classify_stereo(evidence, policy)[0], "inconclusive")


if __name__ == "__main__":
    unittest.main()
