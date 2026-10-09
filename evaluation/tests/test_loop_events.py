"""Measurements needed for independent detector comparison; no accuracy simulation."""

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from benchmarks.loop_events import normalize_loop_event
from modules.evaluation_file_handler.handler import EvaluationFileHandler


STAMP = 1403636579763555584
PAIR = {"query_keyframe_id": 9, "historical_keyframe_id": 2, "query_frame_id": 91,
        "historical_frame_id": 20, "query_map_id": 0, "historical_map_id": 0,
        "query_timestamp_ns": STAMP, "historical_timestamp_ns": STAMP - 1_000_000_000,
        "attempt_id": 1, "stage": "bow_geometry"}


class LoopEventTests(unittest.TestCase):
    def test_transient_markdown_lock_retries_atomic_replacement(self):
        real_replace = Path.replace
        failures = []
        def locked(source, target):
            if target.suffix == ".md" and len(failures) < 2:
                failures.append(1)
                raise PermissionError("Transient sharing violation")
            return real_replace(source, target)
        with tempfile.TemporaryDirectory() as folder, patch.object(Path, "replace", locked), \
                patch("modules.evaluation_file_handler.handler.time.sleep") as sleep:
            path = Path(folder) / "report.json"
            handler = EvaluationFileHandler(path, {}, ["orb"])
            handler.close("complete")
            self.assertEqual(sleep.call_count, 2)
            self.assertIn("**Status:** complete", path.with_suffix(".md").read_text())
            self.assertFalse(path.with_suffix(".md.tmp").exists())

    def test_comparison_joins_on_source_images_not_native_keyframe_ids(self):
        baseline = normalize_loop_event("loop_proposed", PAIR, STAMP, "orb_slam3_dbow2")
        model = normalize_loop_event("loop_proposed", {**PAIR, "query_keyframe_id": 90,
                                     "historical_keyframe_id": 200}, STAMP, "transformer")
        self.assertEqual(baseline["pair_id"], model["pair_id"])
        self.assertEqual(baseline["query_images"], model["query_images"])
        self.assertEqual(baseline["historical_images"]["cam0"], f"mav0/cam0/data/{STAMP - 1_000_000_000}.png")
        self.assertNotIn("pair_id", PAIR)

    def test_invalid_comparison_measurements_fail_explicitly(self):
        cases = [("loop_proposed", {**PAIR, "query_timestamp_ns": float(STAMP)}),
                 ("loop_proposed", {**PAIR, "query_timestamp_ns": STAMP + 1}),
                 ("loop_proposed", {**PAIR, "historical_timestamp_ns": None}),
                 ("loop_decision", {**PAIR, "accepted": "true"}),
                 ("loop_verified", {**PAIR, "accepted": True, "verification_seconds": float("nan")})]
        for kind, payload in cases:
            with self.subTest(kind=kind, payload=payload), self.assertRaises(ValueError):
                normalize_loop_event(kind, payload, STAMP, "orb_slam3_dbow2")

    def test_report_preserves_no_candidate_queries_and_distinct_decision_stages(self):
        query = {"keyframe_id": 9, "frame_id": 91, "map_id": 0}
        events = [("loop_query", {**query, "eligible": False}),
                  ("loop_query", {**query, "eligible": True}),
                  ("loop_proposed", PAIR),
                  ("loop_verified", {**PAIR, "accepted": False, "verification_seconds": 0.001,
                                     "rejection_reason": "bow_matches", "gate_measurements": {
                                         "bow_matches": {"observed": 12, "threshold": 20, "passed": False}},
                                     "diagnostics": {"ransac_usable_correspondences": 8},
                                     "projection_matches": None}),
                  ("loop_proposed", {**PAIR, "attempt_id": 2}),
                  ("loop_verified", {**PAIR, "attempt_id": 2, "accepted": True,
                                     "verification_seconds": 0.002, "projection_matches": 81}),
                  ("loop_decision", {**PAIR, "accepted": True, "stage": "native_final_gate"}),
                  ("constraint_inserted", PAIR)]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "report.json"
            handler = EvaluationFileHandler(path, {}, ["orb"], queue_capacity=1)
            try:
                for number, (kind, payload) in enumerate(events, 1):
                    handler.enqueue("orb", {"event_number": number, "event_type": kind,
                        "sequence_id": "MH_01_easy", "dataset_timestamp_ns": STAMP,
                        "payload": normalize_loop_event(kind, payload, STAMP, "orb_slam3_dbow2")})
                handler.record_status("orb", status="complete", exit_code=0, execution_seconds=2.5)
            finally:
                handler.close("complete")
            report = json.loads(path.read_text())
            case = report["cases"][0]
            for name, count in {"loop_query_count": 2, "eligible_loop_query_count": 1,
                                "proposal_count": 2, "geometric_acceptance_count": 1,
                                "geometric_rejection_count": 1, "loop_decision_count": 1,
                                "detected_loop_count": 1, "constraint_count": 1}.items():
                self.assertEqual(case[name], count)
            self.assertIsNone(case["detection_metrics"]["tp"])
            markdown = path.with_suffix(".md").read_text(encoding="utf-8")
            self.assertIn("**Status:** complete", markdown)
            self.assertIn("| orb | complete | 2 | 1 | 2 | 1 | 1 | 1 | 1 | 1 |", markdown)
            self.assertIn("| orb | Not evaluated | Not evaluated | Not evaluated | Not evaluated | Not evaluated |", markdown)
            self.assertIn("[All recorded events](report/events.jsonl)", markdown)
            self.assertIn("Execution duration (seconds): 2.5", markdown)
            self.assertIn("| bow_matches | 1 | 0 | 1 | 12 | 12 | 20 |", markdown)
            self.assertEqual(case["rejection_reasons"], {"bow_matches": 1})
            self.assertIn("| ransac_usable_correspondences | 1 | 8 | 8 | 8.00 |", markdown)
            stored = [json.loads(line) for line in Path(report["events_file"]).read_text().splitlines()]
            self.assertEqual(stored[0]["payload"]["eligible"], False)
            self.assertEqual(stored[3]["payload"]["accepted"], False)

    def test_failed_run_markdown_reports_errors_and_partial_results(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "failed.json"
            handler = EvaluationFileHandler(path, {}, ["orb"])
            handler.record_status("orb", status="failed", exit_code=1, errors=["Native process failed | timeout"])
            handler.close("failed", "Benchmark failure")
            markdown = path.with_suffix(".md").read_text(encoding="utf-8")
            self.assertIn("**Status:** failed", markdown)
            self.assertIn("Native process failed \\| timeout", markdown)
            self.assertIn("This report is partial", markdown)
            self.assertFalse(path.with_suffix(".md.tmp").exists())

    def test_connected_candidates_are_not_counted_as_geometric_rejections(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "report.json"
            handler = EvaluationFileHandler(path, {}, ["orb"])
            try:
                selection = normalize_loop_event("loop_candidate", {**PAIR,
                    "selection_stage": "database_word_pool", "selection_reason": "direct_connected",
                    "candidate_kind": "loop"}, STAMP, "orb_slam3_dbow2")
                handler.enqueue("orb", {"event_type": "loop_candidate", "payload": selection})
                handler.enqueue("orb", {"event_type": "loop_retrieval", "payload": {"loop_candidates": 0}})
                handler.record_status("orb", status="complete")
            finally:
                handler.close("complete")
            case = json.loads(path.read_text())["cases"][0]
            self.assertEqual(case["candidate_selection"], {"database_word_pool": {"direct_connected": 1}})
            self.assertEqual(case["empty_loop_retrieval_count"], 1)
            self.assertEqual(case["geometric_rejection_count"], 0)
            self.assertIn("| database_word_pool | direct_connected | 1 |", path.with_suffix(".md").read_text())
