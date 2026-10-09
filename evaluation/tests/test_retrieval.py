"""Chronology, ranking, IPC output semantics and native-failure cleanup."""

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from benchmarks.orb_dbow2.replay import make_replay
from benchmarks.retrieval import normalize_retrieval
from modules.evaluation_file_handler.handler import EvaluationFileHandler


class RetrievalTests(unittest.TestCase):
    def payload(self):
        return {"query_timestamp_ns": 30_000_000_000, "eligible_history_count": 2,
                "feature_count": 20, "bow_word_count": 10,
                "timings_ms": {"retrieval": 1.5},
                "candidates": [{"rank": 1, "historical_timestamp_ns": 1, "score": .8},
                               {"rank": 2, "historical_timestamp_ns": 2, "score": .7}]}

    def test_replay_uses_fixed_time_grid_with_irregular_frames(self):
        with tempfile.TemporaryDirectory() as directory:
            sequence = Path(directory)
            camera = sequence / "mav0/cam0"
            (camera / "data").mkdir(parents=True)
            stamps = [100, 100_000_100, 550_000_100, 1_000_000_100, 1_510_000_100]
            (camera / "data.csv").write_text("#timestamp,filename\n" + "".join(f"{stamp},{stamp}.png\n" for stamp in stamps))
            for stamp in stamps:
                (camera / "data" / f"{stamp}.png").touch()
            self.assertEqual([stamp for stamp, _ in make_replay(sequence, 2)], [stamps[i] for i in (0, 2, 3, 4)])
            (camera / "data.csv").write_text("100,100.png\n99,99.png\n")
            with self.assertRaisesRegex(ValueError, "increasing"):
                make_replay(sequence, 2)

    def test_retrieval_rejects_leakage_bad_ranks_and_nonfinite_scores(self):
        for mutation in (lambda p: p["candidates"][0].update(historical_timestamp_ns=p["query_timestamp_ns"]),
                         lambda p: p["candidates"][0].update(score=float("nan")),
                         lambda p: p["candidates"][1].update(score=.9),
                         lambda p: p["candidates"][1].update(rank=3)):
            payload = self.payload()
            mutation(payload)
            with self.assertRaises(ValueError):
                normalize_retrieval(payload, payload["query_timestamp_ns"], "orb_dbow2")

    def test_writer_keeps_candidates_separate_from_accepted_loops(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            handler = EvaluationFileHandler(path, {}, ["orb"], queue_capacity=1)
            def publish(name, payload):
                handler.enqueue("orb", {"event_type": name, "payload": payload})
            try:
                publish("retrieval_setup", {"camera": "cam0", "sample_hz": 2, "temporal_exclusion_seconds": 20,
                        "top_k": 5, "ranking": "score", "imu_usage": "None", "provenance": {"revision": "pinned"}, "replay_sha256": "hash"})
                publish("retrieval_query", self.payload())
                empty = self.payload()
                empty["candidates"] = []
                publish("retrieval_query", empty)
                handler.record_status("orb", status="complete")
            finally:
                handler.close("complete")
            case = json.loads(path.read_text())["cases"][0]
            self.assertEqual(case["image_retrieval"]["candidate_count"], 2)
            self.assertEqual(case["image_retrieval"]["empty_eligible_queries"], 1)
            self.assertEqual(case["detected_loop_count"], 0)
            markdown = path.with_suffix(".md").read_text()
            self.assertIn("not accepted loop closures", markdown)
            self.assertNotIn("Constraints inserted", markdown)
            self.assertIn("not evaluated", markdown)


if __name__ == "__main__":
    unittest.main()
