"""Integration tests for IPC, per-process FIFO output, and process supervision."""

import json
import tempfile
import unittest
from pathlib import Path

import yaml

from loop_eval.infrastructure.evaluation_file_handler.handler import EvaluationFileHandler
from loop_eval.infrastructure.orchestrator.orchestrator import EvaluationRunError, Orchestrator

WORKER = Path(__file__).parent / "fixtures/worker.py"

SRC = Path(__file__).resolve().parents[2] / "src/loop_eval"


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def config(self, modes):
        config = {
            "version": 1,
            "run": {"max_parallel": 2, "timezone": "Asia/Jerusalem", "seed": 17},
            "dataset": {"root": str(self.root)},
            "output": {"root": str(self.root / "output"), "queue_capacity": 1},
            "benchmarks": [
                {
                    "id": f"worker_{index}",
                    "command": ["{python}", str(WORKER), mode],
                    "timeout_seconds": 0.5 if mode == "timeout" else 30,
                }
                for index, mode in enumerate(modes)
            ],
        }
        path = self.root / "config.yaml"
        path.write_text(yaml.safe_dump(config), encoding="utf-8")
        return path

    def run_failure(self, modes):
        with self.assertRaises(EvaluationRunError) as caught:
            Orchestrator(self.config(modes)).run()
        return json.loads(caught.exception.report_path.read_text()), caught.exception.report_path

    def test_parallel_fifo_drain_and_stderr(self):
        path = Orchestrator(self.config(["success", "success"])).run()
        report = json.loads(path.read_text())
        self.assertEqual(report["status"], "complete")
        events = [json.loads(line) for line in Path(report["events_file"]).read_text().splitlines()]
        for case in report["cases"]:
            own = [event for event in events if event["benchmark_id"] == case["benchmark_id"]]
            self.assertEqual([event["event_number"] for event in own], list(range(1, 105)))
            self.assertEqual(case["event_count"], 104)
            self.assertEqual(case["proposal_count"], 100)
            self.assertEqual(case["geometric_acceptance_count"], 1)
            self.assertEqual(case["constraint_count"], 1)
            self.assertIsNone(case["detection_metrics"]["tp"])
            log = path.with_suffix("") / f"{case['benchmark_id']}.stderr.log"
            self.assertEqual(log.read_text().count("diagnostic"), 30000)
        self.assertFalse(path.with_suffix(".json.tmp").exists())

    def test_malformed_events_fail_but_preserve_received_events(self):
        report, path = self.run_failure(["malformed", "success"])
        self.assertEqual(report["status"], "partial")
        failed = report["cases"][0]
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["event_count"], 1)
        self.assertTrue(failed["errors"])
        self.assertTrue(path.exists())

    def test_successful_exit_requires_completed_event(self):
        report, _ = self.run_failure(["no_terminal"])
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["cases"][0]["exit_code"], 0)

    def test_nonzero_exit_is_recorded(self):
        report, _ = self.run_failure(["failed"])
        self.assertEqual(report["cases"][0]["exit_code"], 2)

    def test_timeout_terminates_process(self):
        report, _ = self.run_failure(["timeout"])
        case = report["cases"][0]
        self.assertIn("Benchmark exceeded timeout_seconds", case["errors"])
        self.assertLess(case["execution_seconds"], 20)

    def test_no_benchmarks_does_not_create_fake_report(self):
        with self.assertRaisesRegex(ValueError, "at least one"):
            Orchestrator(self.config([])).run()
        self.assertFalse((self.root / "output").exists())

    def test_exited_adapter_cannot_leave_descendants_holding_pipes(self):
        report, _ = self.run_failure(["orphan"])
        case = report["cases"][0]
        self.assertIn("Benchmark left descendant processes running", case["errors"])
        self.assertLess(case["execution_seconds"], 20)

    def test_singleton_and_exclusive_output_filename(self):
        path = self.root / "report.json"
        handler = EvaluationFileHandler(path, {}, ["worker"])
        self.assertIs(EvaluationFileHandler.instance(), handler)
        with self.assertRaisesRegex(RuntimeError, "already active"):
            EvaluationFileHandler(self.root / "other.json", {}, ["worker"])
        handler.close("complete")
        original = path.read_text()
        with self.assertRaises(FileExistsError):
            EvaluationFileHandler(path, {}, ["worker"])
        self.assertEqual(path.read_text(), original)
        with self.assertRaisesRegex(RuntimeError, "No active"):
            EvaluationFileHandler.instance()


if __name__ == "__main__":
    unittest.main()
