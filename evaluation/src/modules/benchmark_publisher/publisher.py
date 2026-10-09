"""Publish benchmark events to the parent through stdout; send logs to stderr."""

import json
import os
import sys
import threading


class BenchmarkPublisher:
    def __init__(self) -> None:
        self.run_id = os.environ["EVALUATION_RUN_ID"]
        self.benchmark_id = os.environ["EVALUATION_BENCHMARK_ID"]
        self._number = 0
        self._terminal = False
        self._lock = threading.Lock()

    def publish(self, event_type: str, payload: dict | None = None,
                sequence_id: str | None = None, dataset_timestamp_ns: int | None = None) -> None:
        with self._lock:
            if self._terminal:
                raise RuntimeError("Cannot publish after a terminal event")
            if not isinstance(event_type, str) or not event_type:
                raise ValueError("event_type must be a nonempty string")
            if payload is not None and not isinstance(payload, dict):
                raise ValueError("payload must be an object")
            if dataset_timestamp_ns is not None and type(dataset_timestamp_ns) is not int:
                raise ValueError("Dataset timestamps must be integer nanoseconds")
            event = {
                "protocol_version": 1, "run_id": self.run_id,
                "benchmark_id": self.benchmark_id, "event_number": self._number + 1,
                "event_type": event_type, "sequence_id": sequence_id,
                "dataset_timestamp_ns": dataset_timestamp_ns,
                "payload": {} if payload is None else payload,
            }
            line = json.dumps(event, ensure_ascii=True, allow_nan=False)
            sys.stdout.write(line + "\n")
            sys.stdout.flush()
            self._number += 1
            self._terminal = event_type in {"completed", "failed"}
