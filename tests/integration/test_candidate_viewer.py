"""Saved provenance, match gates and bidirectional viewer navigation."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
import yaml

from loop_eval.tasks.feature_matching.viewer.viewer import (
    EvidenceReview,
    PairViewer,
    landmark_gate,
    support_counts,
    xyz_rejects_pair,
)


class CandidateViewerTests(unittest.TestCase):
    def fixture(self, root):
        checks = root / "candidate_checks"
        checks.mkdir()
        images = []
        for index in range(3):
            path = root / f"{index}.png"
            cv2.imwrite(str(path), np.full((240, 320, 3), 50 + index * 30, np.uint8))
            images.append(path)
        replay = root / "replay.tsv"
        replay.write_text("".join(f"{index}\t{path}\n" for index, path in enumerate(images)))
        policy = yaml.safe_load(
            (
                Path(__file__).resolve().parents[2]
                / "configs/evaluation/feature_matching/xyz/config.yaml"
            ).read_text()
        )
        (checks / "provenance.json").write_text(
            json.dumps(
                {
                    "policy": policy,
                    "input_and_code_sha256": {
                        str(replay): hashlib.sha256(replay.read_bytes()).hexdigest()
                    },
                }
            )
        )
        landmarks = [
            {
                "query_feature_xy": [20, 30],
                "historical_feature_xy": [25, 35],
                "query_world_xyz": [1, 2, 3],
                "historical_world_xyz": [1.02, 2, 3],
                "xyz_error_m": 0.02,
                "mahalanobis_squared": 0.2,
                "three_sigma_radius_m": 0.3,
                "cross_reprojection_px": [8, 9],
                "consistent": False,
            },
            {
                "query_feature_xy": [100, 120],
                "historical_feature_xy": [110, 125],
                "query_world_xyz": [2, 1, 4],
                "historical_world_xyz": [2, 1, 4],
                "xyz_error_m": 0,
                "mahalanobis_squared": 0,
                "three_sigma_radius_m": 0.3,
                "cross_reprojection_px": [0, 0],
                "consistent": True,
            },
        ]
        rows = []
        for query, outcome in ((1, "suspicious"), (2, "overlap_supported"), (2, "suspicious")):
            rows.append(
                {
                    "query_timestamp_ns": query,
                    "historical_timestamp_ns": 0,
                    "rank": 1,
                    "outcome": outcome,
                    "reasons": ["stereo_world_or_reprojection_disagrees"],
                    "pose_evidence": {
                        "available": True,
                        "camera_position_distance_m": 0.5,
                        "camera_orientation_difference_degrees": 5,
                    },
                    "measurements": {
                        "match_count": 26,
                        "query_image_sha256": hashlib.sha256(
                            images[query].read_bytes()
                        ).hexdigest(),
                        "historical_image_sha256": hashlib.sha256(
                            images[0].read_bytes()
                        ).hexdigest(),
                    },
                    "stereo": {"landmarks": landmarks},
                }
            )
        (checks / "pairs.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
        return EvidenceReview(checks, root), images

    def test_filter_navigation_click_selection_and_exact_source_image_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            review, images = self.fixture(Path(directory))
            self.assertEqual(len(review.pairs), 3)
            viewer = PairViewer(review)
            viewer.move(-1)
            self.assertEqual(viewer.index, 0)
            viewer.move(1)
            self.assertEqual(viewer.index, 1)
            viewer.move(1)
            self.assertEqual(viewer.index, 2)
            viewer.move(1)
            self.assertEqual(viewer.index, 2)
            viewer.move(-1)
            canvas = viewer.render()
            self.assertEqual(canvas.shape, (1050, 1440, 3))
            left, top, scale, _, _ = viewer.image_boxes[1]
            viewer.mouse(
                cv2.EVENT_LBUTTONDOWN,
                round(left + 110 * scale),
                round(top + 125 * scale),
                None,
                None,
            )
            self.assertEqual(viewer.feature, 1)
            viewer.select_feature(1)
            self.assertEqual(viewer.feature, 0)
            images[0].write_bytes(b"modified image")
            with self.assertRaisesRegex(ValueError, "differs"):
                review.load_images(review.pairs[0])

    def test_xyz_and_reprojection_colors_use_saved_thresholds(self):
        policy = {
            "stereo_world_mahalanobis_squared_maximum": 11.345,
            "stereo_cross_reprojection_px": 7,
        }
        point = {"mahalanobis_squared": 11.345, "cross_reprojection_px": [7, 7]}
        self.assertEqual(landmark_gate(point, policy), "passed")
        point["cross_reprojection_px"] = [7.1, None]
        self.assertEqual(landmark_gate(point, policy), "reprojection_failed")
        point["mahalanobis_squared"] = 12
        self.assertEqual(landmark_gate(point, policy), "both_failed")
        point["cross_reprojection_px"] = [1, 1]
        self.assertEqual(landmark_gate(point, policy), "xyz_failed")

    def test_keyboard_navigation_and_window_close(self):
        with tempfile.TemporaryDirectory() as directory:
            review, _ = self.fixture(Path(directory))
            viewer = PairViewer(review)
            with (
                patch("cv2.namedWindow"),
                patch("cv2.resizeWindow"),
                patch("cv2.setMouseCallback"),
                patch("cv2.imshow"),
                patch("cv2.destroyAllWindows"),
                patch("cv2.getWindowProperty", return_value=1),
                patch(
                    "cv2.waitKeyEx",
                    side_effect=[2555904, ord("]"), 2424832, ord("l"), ord("v"), ord("q")],
                ),
            ):
                viewer.run()
            self.assertEqual(viewer.index, 0)
            self.assertFalse(viewer.all_lines)
            self.assertFalse(viewer.overlay)

    def test_overlay_uses_only_post_ransac_pairs_including_untested_depth(self):
        viewer = PairViewer.__new__(PairViewer)
        retained = {
            "query_feature_id": 1,
            "historical_feature_id": 5,
            "query_feature_xy": [10, 20],
            "historical_feature_xy": [30, 40],
        }
        untested = {**retained, "query_feature_id": 2}
        rejected = {**retained, "query_feature_id": 3}
        pair = {
            "ransac": {"rejected_feature_pairs": [[3, 5]]},
            "feature_matches": [retained, untested, rejected],
            "stereo": {"landmarks": [{**retained, "mahalanobis_squared": 0.1}]},
        }
        visible = viewer.visible_landmarks(pair)
        self.assertEqual([p["query_feature_id"] for p in visible], [1, 2])
        self.assertIn("mahalanobis_squared", visible[0])
        self.assertNotIn("mahalanobis_squared", visible[1])

    def test_modified_replay_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            review, _ = self.fixture(root)
            (root / "replay.tsv").write_text("modified replay")
            with self.assertRaisesRegex(ValueError, "Replay differs"):
                EvidenceReview(review.checks, root)

    def test_three_buttons_partition_all_candidates_and_handle_missing_landmarks(self):
        with tempfile.TemporaryDirectory() as directory:
            review, _ = self.fixture(Path(directory))
            review.policy.update(minimum_inlier_ratio=0.04, minimum_image_coverage=0.05)
            review.all_pairs[0]["stereo"] = {"landmarks": []}
            viewer = PairViewer(review)
            viewer.switch_xyz("supported")
            self.assertEqual(len(review.pairs), 2)
            viewer.render()
            viewer.mouse(cv2.EVENT_LBUTTONDOWN, 1100, 115, None, None)
            self.assertEqual(viewer.xyz_mode, "not supported")
            self.assertEqual(len(review.pairs), 1)
            self.assertEqual(review.pairs[0]["viewer_xyz_status"], "insufficient evidence")
            self.assertEqual(viewer.index, 0)
            self.assertIsNone(viewer._loaded_index)
            viewer.render()
            viewer.select_feature(1)
            viewer.mouse(cv2.EVENT_LBUTTONDOWN, 100, 115, None, None)
            self.assertEqual(viewer.xyz_mode, "all")
            self.assertEqual(len(review.pairs), 3)
            supported_ids = {id(p) for p in viewer.xyz_groups["supported"]}
            other_ids = {id(p) for p in viewer.xyz_groups["not supported"]}
            self.assertFalse(supported_ids & other_ids)
            self.assertEqual(supported_ids | other_ids, {id(p) for p in viewer.xyz_groups["all"]})
            viewer.mouse(cv2.EVENT_LBUTTONDOWN, 600, 115, None, None)
            self.assertEqual(viewer.xyz_mode, "supported")

    def test_new_support_denominator_is_all_reported_matches(self):
        pair = {"measurements": {"match_count": 26}, "stereo": {"landmarks": [{}, {}]}}
        self.assertEqual(
            support_counts(pair, {"version": 4, "minimum_inlier_ratio": 0.4}), (26, 11, 11)
        )

    def test_xyz_pair_rejection_requires_count_coverage_and_low_xyz_pass_ratio(self):
        policy = {
            "minimum_stereo_landmarks": 20,
            "minimum_image_coverage": 0.15,
            "stereo_world_mahalanobis_squared_maximum": 11.345,
            "contradiction_maximum_inlier_ratio": 0.1,
        }
        pair = {
            "stereo": {
                "paired_coverage": 0.2,
                "landmarks": [
                    {"mahalanobis_squared": 12, "cross_reprojection_px": [0, 0]} for _ in range(20)
                ],
            }
        }
        self.assertTrue(xyz_rejects_pair(pair, policy))
        pair["stereo"]["landmarks"][0]["mahalanobis_squared"] = 0
        pair["stereo"]["landmarks"][1]["mahalanobis_squared"] = 0
        self.assertTrue(xyz_rejects_pair(pair, policy))
        pair["stereo"]["landmarks"][2]["mahalanobis_squared"] = 0
        self.assertFalse(xyz_rejects_pair(pair, policy))
        pair["stereo"]["landmarks"][2]["mahalanobis_squared"] = 12
        pair["stereo"]["paired_coverage"] = 0.1
        self.assertFalse(xyz_rejects_pair(pair, policy))
        pair["stereo"]["paired_coverage"] = 0.2
        pair["stereo"]["landmarks"].pop()
        self.assertFalse(xyz_rejects_pair(pair, policy))

    def test_viewer_excludes_missing_ground_truth_in_older_saved_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            review, _ = self.fixture(Path(directory))
            path = review.checks / "pairs.jsonl"
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            rows[0]["pose_evidence"]["available"] = False
            path.write_text("".join(json.dumps(row) + "\n" for row in rows))
            review = EvidenceReview(review.checks, directory)
            self.assertEqual(len(review.all_pairs), 2)
            self.assertEqual(review.excluded_count, 1)
            self.assertTrue(all(row["pose_evidence"]["available"] for row in review.all_pairs))
            viewer = PairViewer(review)
            with patch("loop_eval.tasks.feature_matching.viewer.viewer.label") as draw:
                viewer.render()
            messages = [str(call.args[1]) for call in draw.call_args_list]
            self.assertTrue(any("GT-eligible 2 / excluded 1" in text for text in messages))
            self.assertTrue(any("M^2 <= 11.345" in text for text in messages))
            viewer.switch_xyz("supported")
            self.assertEqual(review.pairs, [])
            viewer.move(1)
            viewer.select_feature(1)
            self.assertEqual(viewer.render().shape, (1050, 1440, 3))
            viewer.mouse(cv2.EVENT_LBUTTONDOWN, 100, 115, None, None)
            self.assertEqual(viewer.xyz_mode, "all")

    def test_navigation_buttons_and_inspector_feature_controls(self):
        with tempfile.TemporaryDirectory() as directory:
            review, _ = self.fixture(Path(directory))
            viewer = PairViewer(review)
            viewer.render()
            viewer.mouse(cv2.EVENT_LBUTTONDOWN, 1350, 170, None, None)
            self.assertEqual(viewer.index, 1)
            viewer.render()
            viewer.mouse(cv2.EVENT_LBUTTONDOWN, 1200, 170, None, None)
            self.assertEqual(viewer.index, 0)
            viewer.select_feature(-1)
            self.assertEqual(viewer.feature, 1)

    def test_retrieval_metadata_is_read_only_and_hash_verified(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            review, _ = self.fixture(root)
            trace = root / "retrieval.jsonl"
            trace.write_text(
                json.dumps(
                    {
                        "query_timestamp_ns": 1,
                        "eligible_history_count": 12,
                        "feature_count": 1000,
                        "bow_word_count": 800,
                        "timings_ms": {"retrieval": 0.5},
                        "candidates": [{"historical_timestamp_ns": 0, "rank": 1, "score": 0.125}],
                    }
                )
            )
            provenance = review.checks / "provenance.json"
            data = json.loads(provenance.read_text())
            data["input_and_code_sha256"][str(trace)] = hashlib.sha256(
                trace.read_bytes()
            ).hexdigest()
            provenance.write_text(json.dumps(data))
            review = EvidenceReview(review.checks, root)
            viewer = PairViewer(review)
            with patch("loop_eval.tasks.feature_matching.viewer.viewer.label") as draw:
                viewer.render()
            messages = [str(call.args[1]) for call in draw.call_args_list]
            self.assertTrue(any("BoW score 0.125000" in text for text in messages))
            trace.write_text("modified")
            with self.assertRaisesRegex(ValueError, "Retrieval trace differs"):
                EvidenceReview(review.checks, root)

    def test_copy_flow_reports_current_pair_selected_match_and_saved_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            review, _ = self.fixture(Path(directory))
            viewer = PairViewer(review)
            viewer.move(1)
            viewer.select_feature(1)
            report = viewer.report_text()
            self.assertIn("Current timestamp (ns): 2", report)
            self.assertIn("Selected match: 2 / 2", report)
            self.assertIn('"query_world_xyz"', report)
            self.assertIn('"saved_policy"', report)
            self.assertIn("01  RETRIEVAL", report)
            self.assertIn("XYZ gate: M^2 <= 11.345", report)
            with patch("loop_eval.tasks.feature_matching.viewer.viewer.copy_text") as copied:
                viewer.mouse(cv2.EVENT_LBUTTONDOWN, 1300, 1030, None, None)
            copied.assert_called_once_with(report)
            self.assertEqual(viewer.copy_status, "Copied. Paste into chat.")
            self.assertTrue(viewer.dirty)
            viewer.move(-1)
            self.assertEqual(viewer.copy_status, "")
            with (
                patch(
                    "loop_eval.tasks.feature_matching.viewer.viewer.copy_text",
                    side_effect=OSError("busy"),
                ),
                patch("sys.stderr"),
            ):
                viewer.copy_flow()
            self.assertIn("Copy failed", viewer.copy_status)


if __name__ == "__main__":
    unittest.main()
