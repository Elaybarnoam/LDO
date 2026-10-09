"""Reference-frame math, ambiguous evidence, and real offline checker integration."""

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np
from scipy.spatial.transform import Rotation
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tasks.feature_matching.xyz.evaluator import check_trace, load_policy
from tasks.feature_matching.xyz.geometry import classify, reference_errors
from tasks.feature_matching.xyz.poses import CameraPoses
from modules.evaluation_file_handler.handler import EvaluationFileHandler

CONFIG = Path(__file__).resolve().parents[1] / "src/tasks/feature_matching/xyz/config.yaml"


def export_fixture_orb(root, path):
    """Synthetic parser/math fixture only; production exports upstream ORB."""
    import struct
    from tasks.feature_matching.xyz.orb_features import DTYPE
    image = cv2.imread(str(path), 0)
    keys, descriptors = cv2.ORB_create(nfeatures=1200, edgeThreshold=16, fastThreshold=10).detectAndCompute(image, None)
    rows = np.zeros(len(keys), DTYPE)
    rows["raw"] = rows["rectified"] = [k.pt for k in keys]
    rows["angle"] = [k.angle for k in keys]
    rows["octave"] = [k.octave for k in keys]
    rows["descriptor"] = descriptors
    folder = root / "orb_features"
    folder.mkdir(exist_ok=True)
    data = b"LDORB001" + struct.pack("<III",len(keys),image.shape[1],image.shape[0]) + rows.tobytes()
    export = folder / f"{path.stem}_{path.parents[1].name}.orb"
    export.write_bytes(data)
    import hashlib
    manifest_path = folder / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"exports": {}}
    manifest["exports"][export.name] = {"sha256": hashlib.sha256(data).hexdigest(), "image_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    manifest_path.write_text(json.dumps(manifest))


class CandidateEvaluatorTests(unittest.TestCase):
    def test_orb_exports_bind_features_to_exact_source_images(self):
        from tasks.feature_matching.xyz.orb_features import read_features
        from tasks.feature_matching.xyz.geometry import ImageGeometry
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.fixture(root)
            image = root / "mav0/cam0/data/0.png"
            points, descriptors, size = read_features(root / "orb_features", image)
            self.assertEqual(descriptors.dtype, np.uint8)
            self.assertEqual(descriptors.shape[1], 32)
            self.assertEqual(size, (320, 240))
            geometry = ImageGeometry(root, load_policy(CONFIG))
            self.assertFalse(hasattr(geometry, "extractor"))
            checked = geometry.check(image, image, np.eye(4), 0)
            self.assertGreater(len(checked["feature_matches"]), 20)
            first = checked["feature_matches"][0]
            np.testing.assert_allclose(first["query_feature_xy"], points[first["query_feature_id"]])
            self.assertEqual(first["hamming_distance"], 0)
            image.write_bytes(image.read_bytes() + b"changed")
            with self.assertRaisesRegex(ValueError, "differs from manifest"):
                read_features(root / "orb_features", image)

    def test_reference_epipolar_math_with_real_projected_3d_points(self):
        rng = np.random.default_rng(10)
        points = rng.uniform([-1, -1, 3], [1, 1, 6], size=(60, 3))
        k = np.array([[300, 0, 160], [0, 300, 120], [0, 0, 1]], dtype=float)
        relative = np.eye(4)
        relative[:3, :3] = Rotation.from_euler("z", .12).as_matrix()
        relative[:3, 3] = [.3, .1, 0]
        def project(data):
            projected = data @ k.T
            return projected[:, :2]/projected[:, 2:]
        query = project(points)
        history = project(points @ relative[:3, :3].T + relative[:3, 3])
        errors, method = reference_errors(query, history, k, relative, .01)
        self.assertEqual(method, "reference_epipolar_sampson")
        self.assertLess(float(errors.max()), 1e-10)
        incorrect = history.copy()
        incorrect[:, 1] += 40
        errors, _ = reference_errors(query, incorrect, k, relative, .01)
        self.assertGreater(float(np.median(errors)), 20)
        relative[:3, 3] = 0
        rotation_history = project(points @ relative[:3, :3].T)
        errors, method = reference_errors(query, rotation_history, k, relative, .01)
        self.assertEqual(method, "reference_rotation_reprojection")
        self.assertLess(float(errors.max()), 1e-10)

    def test_weak_matches_and_missing_pose_never_become_false_positive_labels(self):
        policy = load_policy(CONFIG)
        measurement = {"reference_pose_available": True, "match_count": 10,
                       "reference_inliers": 0, "reference_inlier_ratio": 0,
                       "reference_coverage": 0, "homography_inliers": 0, "homography_coverage": 0}
        self.assertEqual(classify(measurement, policy)[0], "inconclusive")
        measurement.update(match_count=100, homography_inliers=80, homography_coverage=.5)
        self.assertEqual(classify(measurement, policy)[0], "suspicious")
        measurement["reference_pose_available"] = False
        self.assertEqual(classify(measurement, policy)[0], "inconclusive")

    def fixture(self, root, contradiction=False):
        cam, truth = root / "mav0/cam0", root / "mav0/state_groundtruth_estimate0"
        (cam / "data").mkdir(parents=True)
        truth.mkdir()
        transform = {"rows": 4, "cols": 4, "data": np.eye(4).ravel().tolist()}
        calibration = {"T_BS": transform, "camera_model": "pinhole", "distortion_model": "radial-tangential",
                       "intrinsics": [200, 200, 160, 120], "distortion_coefficients": [0, 0, 0, 0], "resolution": [320, 240]}
        (cam / "sensor.yaml").write_text(yaml.safe_dump(calibration))
        (truth / "sensor.yaml").write_text(yaml.safe_dump({"T_BS": transform}))
        rotation = Rotation.from_euler("z", 1.0).as_quat() if contradiction else [0, 0, 0, 1]
        translation = [1, 0, 0] if contradiction else [0, 0, 0]
        (truth / "data.csv").write_text("#timestamp,p,q\n0,0,0,0,1,0,0,0\n" + "21000000000," + ",".join(map(str, [*translation, rotation[3], *rotation[:3]])) + "\n")
        texture = np.random.default_rng(8).integers(0, 256, size=(240, 320), dtype=np.uint8)
        image = cv2.GaussianBlur(texture, (3, 3), .7)
        replay = root / "replay.tsv"
        replay.write_text("".join(f"{stamp}\t{cam/'data'/f'{stamp}.png'}\n" for stamp in (0, 21_000_000_000)))
        for stamp in (0, 21_000_000_000):
            cv2.imwrite(str(cam / "data" / f"{stamp}.png"), image)
            export_fixture_orb(root, cam / "data" / f"{stamp}.png")
        trace = root / "trace.jsonl"
        rows = [{"query_timestamp_ns": 0, "candidates": []}, {"query_timestamp_ns": 21_000_000_000,
                 "candidates": [{"historical_timestamp_ns": 0, "rank": 1, "score": .999}]}]
        trace.write_text("".join(json.dumps(row) + "\n" for row in rows))
        return replay, trace

    def test_offline_checker_support_and_contradiction_do_not_depend_on_score(self):
        for contradiction, outcome in ((False, "overlap_supported"), (True, "suspicious")):
            with self.subTest(outcome=outcome), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                replay, trace = self.fixture(root, contradiction)
                # This test exercises the retained 2D-only mode; dedicated
                # stereo tests provide both calibrated cameras.
                policy = load_policy(CONFIG)
                policy["stereo_enabled"] = False
                config = root / "config.yaml"
                config.write_text(yaml.safe_dump(policy))
                original = trace.read_bytes()
                result = check_trace(root, replay, trace, root / "checks", config)
                self.assertEqual(result["outcome_counts"], {outcome: 1})
                self.assertEqual(trace.read_bytes(), original)
                pair = json.loads((root / "checks/pairs.jsonl").read_text())
                self.assertIsNone(pair["accuracy_label"])
                self.assertGreater(pair["measurements"]["match_count"], 25)
                # Score deliberately removed; evidence outcome must remain identical.
                rows = [json.loads(line) for line in trace.read_text().splitlines()]
                rows[1]["candidates"][0].pop("score")
                trace.write_text("".join(json.dumps(row) + "\n" for row in rows))
                second = check_trace(root, replay, trace, root / "checks2", config)
                self.assertEqual(second["outcome_counts"], result["outcome_counts"])

    def test_camera_lever_arm_and_timestamp_tolerance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            path = root / "mav0/cam0/sensor.yaml"
            calibration = yaml.safe_load(path.read_text())
            transform = np.eye(4)
            transform[0, 3] = 1
            calibration["T_BS"]["data"] = transform.ravel().tolist()
            path.write_text(yaml.safe_dump(calibration))
            (root / "mav0/state_groundtruth_estimate0/data.csv").write_text("#timestamp,p,q\n0,0,0,0,1,0,0,0\n21000000000,0,0,0,0.7071067811865476,0,0,0.7071067811865476\n")
            poses = CameraPoses(root, 10)
            relative, evidence = poses.relative(21_000_000_000, 0)
            self.assertAlmostEqual(evidence["camera_position_distance_m"], 2**.5)
            self.assertAlmostEqual(evidence["camera_orientation_difference_degrees"], 90)
            self.assertIsNone(poses.get(100_000_000))
            self.assertIsNone(poses.get(-1))
            self.assertIsNone(poses.get(21_000_000_001))

    def test_missing_ground_truth_is_excluded_before_feature_check_and_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            replay, trace = self.fixture(root)
            # History is outside GT coverage; the query has an exact reference.
            (root / "mav0/state_groundtruth_estimate0/data.csv").write_text("21000000000,0,0,0,1,0,0,0\n")
            policy = load_policy(CONFIG)
            policy["stereo_enabled"] = False
            config = root / "config.yaml"
            config.write_text(yaml.safe_dump(policy))
            report_path = root / "report.json"
            handler = EvaluationFileHandler(report_path, {}, ["orb"], queue_capacity=4)
            try:
                handler.enqueue("orb", {"event_type": "retrieval_setup", "payload": {
                    "camera": "cam0", "sample_hz": 2, "temporal_exclusion_seconds": 20, "top_k": 5,
                    "ranking": "score", "imu_usage": "None", "provenance": {"revision": "test"}, "replay_sha256": "hash"}})
                handler.enqueue("orb", {"event_type": "retrieval_query", "payload": {
                    "query_timestamp_ns": 21_000_000_000, "eligible_history_count": 1, "feature_count": 100,
                    "bow_word_count": 50, "timings_ms": {},
                    "candidates": [{"historical_timestamp_ns": 0, "rank": 1, "score": .999}]}})
                with patch("tasks.feature_matching.xyz.evaluator.ImageGeometry.check", side_effect=AssertionError("Excluded pairs must never reach geometry")):
                    result = check_trace(root, replay, trace, root / "checks", config,
                                         on_event=lambda name, payload, stamp=None: handler.enqueue("orb", {"event_type": name, "payload": payload}))
            finally:
                handler.close("complete")
            self.assertEqual(result["returned_pairs"], 1)
            self.assertEqual(result["checked_pairs"], 0)
            self.assertEqual(result["excluded_pairs"], 1)
            self.assertEqual(result["outcome_counts"], {})
            self.assertEqual((root / "checks/pairs.jsonl").read_text(), "")
            exclusion = json.loads((root / "checks/excluded_pairs.jsonl").read_text())
            self.assertEqual(exclusion["missing_reference_poses"], {"historical": "before_ground_truth_start"})
            review = json.loads(report_path.read_text())["cases"][0]["candidate_evaluation"]
            self.assertEqual(review["excluded_pairs"], 1)
            self.assertEqual(review["checked_pairs"], 0)
            self.assertIn("1 pairs excluded", report_path.with_suffix(".md").read_text())


if __name__ == "__main__":
    unittest.main()
