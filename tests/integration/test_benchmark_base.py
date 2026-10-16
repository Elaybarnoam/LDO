"""Verify inherited lifecycle behavior through its public interface."""

import io
import unittest
from contextlib import redirect_stderr
from unittest.mock import Mock

from loop_eval.benchmarks import Benchmark
from loop_eval.infrastructure.benchmark_publisher.publisher import BenchmarkPublisher


class BenchmarkTests(unittest.TestCase):
    def test_inherited_lifecycle_and_measurement_helpers(self):
        publisher = Mock(spec=BenchmarkPublisher)
        order = []

        class Example(Benchmark):
            def setup(self):
                order.append("setup")

            def execute(self):
                order.append("execute")
                self.loop_proposed(10, 2, 123)
                self.loop_verified(10, 2, False, 123)
                return {"frames": 5}

            def cleanup(self):
                order.append("cleanup")

        def publish(event_type, *args):
            order.append(event_type)

        publisher.publish.side_effect = publish
        benchmark = Example("MH_01_easy", publisher)
        self.assertEqual(benchmark.run(), 0)
        self.assertEqual(
            order,
            [
                "started",
                "setup",
                "execute",
                "loop_proposed",
                "loop_verified",
                "cleanup",
                "completed",
            ],
        )
        proposal = publisher.publish.call_args_list[1]
        self.assertEqual(proposal.args[2:], ("MH_01_easy", 123))
        self.assertEqual(publisher.publish.call_args.args[1]["result"], {"frames": 5})
        with self.assertRaisesRegex(RuntimeError, "only run once"):
            benchmark.run()

    def test_setup_failure_still_cleans_up_and_reports_failure(self):
        publisher = Mock(spec=BenchmarkPublisher)
        cleanup = Mock()

        class Example(Benchmark):
            def setup(self):
                raise ValueError("missing executable")

            def execute(self):
                raise AssertionError("Must not execute after setup failure")

            def cleanup(self):
                cleanup()

        with redirect_stderr(io.StringIO()):
            self.assertEqual(Example(publisher=publisher).run(), 1)
        cleanup.assert_called_once()
        self.assertEqual(publisher.publish.call_args.args[0], "failed")
        self.assertIn("missing executable", publisher.publish.call_args.args[1]["errors"][0])

    def test_cleanup_failure_prevents_successful_completion(self):
        publisher = Mock(spec=BenchmarkPublisher)

        class Example(Benchmark):
            def execute(self):
                return {}

            def cleanup(self):
                raise OSError("native child cleanup failed")

        with redirect_stderr(io.StringIO()):
            self.assertEqual(Example(publisher=publisher).run(), 1)
        self.assertEqual(publisher.publish.call_args.args[0], "failed")

    def test_adapter_cannot_publish_premature_completion(self):
        publisher = Mock(spec=BenchmarkPublisher)

        class Example(Benchmark):
            def execute(self):
                self.publish("completed")

        with redirect_stderr(io.StringIO()):
            self.assertEqual(Example(publisher=publisher).run(), 1)
        self.assertEqual(
            [call.args[0] for call in publisher.publish.call_args_list], ["started", "failed"]
        )

    def test_execute_is_required(self):
        with self.assertRaises(TypeError):
            Benchmark(publisher=Mock(spec=BenchmarkPublisher))


if __name__ == "__main__":
    unittest.main()
