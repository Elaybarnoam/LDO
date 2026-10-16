"""Inherited lifecycle and event publishing for concrete benchmark adapters."""

import json
import sys
import time
import traceback
from abc import ABC, abstractmethod
from typing import final

from loop_eval.benchmarks.loop_events import normalize_loop_event
from loop_eval.benchmarks.retrieval import normalize_retrieval
from loop_eval.infrastructure.benchmark_publisher.publisher import BenchmarkPublisher


class Benchmark(ABC):
    """Override execute; optionally override setup and cleanup.

    One instance represents one process/case and may be run exactly once.
    The orchestrator still supervises processes; this class provides their
    common adapter lifecycle and publishes measurements to the parent.
    """

    def __init__(
        self, sequence_id: str | None = None, publisher: BenchmarkPublisher | None = None
    ) -> None:
        self.sequence_id = sequence_id
        self._publisher = publisher if publisher is not None else BenchmarkPublisher()
        self._phase = "new"

    def setup(self) -> None:
        """Optional preflight and native-session initialization hook."""
        return None

    @abstractmethod
    def execute(self) -> dict | None:
        """Execute the actual benchmark and return JSON-compatible result metadata."""

    def cleanup(self) -> None:
        """Optional hook to release resources and await native children."""
        return None

    def publish(
        self, event_type: str, payload: dict | None = None, dataset_timestamp_ns: int | None = None
    ) -> None:
        if self._phase not in {"running", "cleaning"}:
            raise RuntimeError("Measurements may only be published during the benchmark lifecycle")
        if event_type in {"started", "completed", "failed"}:
            raise ValueError("Lifecycle events are owned by Benchmark.run()")
        self._publisher.publish(event_type, payload, self.sequence_id, dataset_timestamp_ns)

    @staticmethod
    def log(message: str) -> None:
        """Diagnostic output never enters the stdout event protocol."""
        print(message, file=sys.stderr, flush=True)

    def publish_loop_measurement(
        self, event_type: str, payload: dict, detector_id: str, dataset_timestamp_ns: int
    ) -> None:
        """Shared, comparison-ready publishing inherited by real detector adapters."""
        data = normalize_loop_event(event_type, payload, dataset_timestamp_ns, detector_id)
        self.publish(event_type, data, dataset_timestamp_ns)

    def loop_proposed(
        self,
        query_keyframe_id: int,
        historical_keyframe_id: int,
        dataset_timestamp_ns: int | None = None,
    ) -> None:
        self.publish(
            "loop_proposed",
            {
                "query_keyframe_id": query_keyframe_id,
                "historical_keyframe_id": historical_keyframe_id,
            },
            dataset_timestamp_ns,
        )

    def publish_retrieval(self, payload: dict, detector_id: str, timestamp_ns: int) -> None:
        self.publish(
            "retrieval_query", normalize_retrieval(payload, timestamp_ns, detector_id), timestamp_ns
        )

    def evaluate_candidates(
        self, sequence, replay, trace, output, config, feature_root=None, correspondence_source=None
    ):
        """Offline independent evidence checking shared by detector adapters."""
        from loop_eval.tasks.feature_matching.xyz.evaluator import check_trace

        return check_trace(
            sequence,
            replay,
            trace,
            output,
            config,
            on_event=self.publish,
            on_log=self.log,
            feature_root=feature_root,
            correspondence_source=correspondence_source,
        )

    def loop_verified(
        self,
        query_keyframe_id: int,
        historical_keyframe_id: int,
        accepted: bool,
        dataset_timestamp_ns: int | None = None,
    ) -> None:
        if type(accepted) is not bool:
            raise ValueError("accepted must be an explicit boolean")
        self.publish(
            "loop_verified",
            {
                "query_keyframe_id": query_keyframe_id,
                "historical_keyframe_id": historical_keyframe_id,
                "accepted": accepted,
            },
            dataset_timestamp_ns,
        )

    def constraint_inserted(
        self,
        query_keyframe_id: int,
        historical_keyframe_id: int,
        dataset_timestamp_ns: int | None = None,
    ) -> None:
        self.publish(
            "constraint_inserted",
            {
                "query_keyframe_id": query_keyframe_id,
                "historical_keyframe_id": historical_keyframe_id,
            },
            dataset_timestamp_ns,
        )

    @final
    def run(self) -> int:
        """Template method: publish lifecycle, execute hooks, and always clean up.

        Returns a process exit code. Adapter entry points use SystemExit(run()).
        Cleanup completes before any terminal event is emitted.
        """
        if self._phase != "new":
            raise RuntimeError("A benchmark instance can only run once")
        self._phase = "running"
        started = time.monotonic()
        errors, result, exit_code = [], {}, 0
        try:
            self._publisher.publish("started", {}, self.sequence_id)
            self.setup()
            value = self.execute()
            if value is not None:
                if not isinstance(value, dict):
                    raise ValueError("execute() must return a dictionary or None")
                json.dumps(value, allow_nan=False)
                result = value
        except (Exception, KeyboardInterrupt) as error:
            errors.append(f"{type(error).__name__}: {error}")
            exit_code = 130 if isinstance(error, KeyboardInterrupt) else 1
            traceback.print_exc(file=sys.stderr)
        finally:
            self._phase = "cleaning"
            try:
                self.cleanup()
            except (Exception, KeyboardInterrupt) as error:
                errors.append(f"cleanup {type(error).__name__}: {error}")
                exit_code = exit_code or 1
                traceback.print_exc(file=sys.stderr)
            self._phase = "finished"
        duration = time.monotonic() - started
        if errors:
            self._publisher.publish(
                "failed", {"errors": errors, "execution_seconds": duration}, self.sequence_id
            )
        else:
            self._publisher.publish(
                "completed", {"result": result, "execution_seconds": duration}, self.sequence_id
            )
        return exit_code
