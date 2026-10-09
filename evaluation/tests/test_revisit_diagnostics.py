"""Validate read-only evidence generation without treating it as loop ground truth."""

import json
from pathlib import Path
import sys
import tempfile
import unittest

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from benchmarks.orb_slam3.diagnostics.revisit import validate_revisit


class RevisitDiagnosticTests(unittest.TestCase):
    def test_missing_ground_truth_is_explicitly_unavailable(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.assertEqual(validate_revisit(root / "trace.jsonl", root, root)["status"], "unavailable")

    def test_image_evidence_preserves_connected_selection_and_is_not_an_accuracy_label(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            images = root / "mav0/cam0/data"
            images.mkdir(parents=True)
            truth = root / "mav0/state_groundtruth_estimate0"
            truth.mkdir()
            h, q = 1403636579763555584, 1403636609763555584
            (truth / "data.csv").write_text(f"#timestamp,position,quaternion\n{h},0,0,0,1,0,0,0\n{q},0,0,0,1,0,0,0\n")
            image = np.random.default_rng(42).integers(0, 256, (240, 320), dtype=np.uint8)
            for stamp in (h, q):
                cv2.imwrite(str(images / f"{stamp}.png"), image)
            trace = root / "trace.jsonl"
            trace.write_text(json.dumps({"event_type": "loop_candidate", "payload": {
                "query_timestamp_ns": q, "historical_timestamp_ns": h,
                "query_keyframe_id": 7, "historical_keyframe_id": 2, "candidate_kind": "loop",
                "selection_stage": "database_word_pool", "selection_reason": "direct_connected"}}) + "\n")
            result = validate_revisit(trace, root, root)
            self.assertEqual(result["status"], "visual_overlap_supported")
            self.assertFalse(result["accuracy_label"])
            self.assertGreaterEqual(result["homography_inliers"], 25)
            self.assertEqual(result["selection_history"], [{"stage": "database_word_pool", "reason": "direct_connected"}])
            self.assertEqual((root / result["query_image"]).read_bytes(), (images / f"{q}.png").read_bytes())
            self.assertNotIn("accepted", result)
