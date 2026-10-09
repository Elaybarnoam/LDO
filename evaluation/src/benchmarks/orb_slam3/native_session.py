"""Native process execution and strict, ordered trace translation."""

import json
import math
import os
from pathlib import Path
import subprocess
import time


EVENTS = {"instrumentation_ready", "keyframe_created", "loop_query", "loop_retrieval", "loop_candidate", "loop_proposed", "loop_verified", "loop_decision",
          "constraint_inserted", "map_merge", "map_merge_proposed", "map_merge_verified", "timing", "native_finished"}


class NativeSession:
    def __init__(self, command: list[str], workspace: Path, revision: str, library_dirs=()):
        self.command, self.workspace, self.revision = command, workspace, revision
        self.library_dirs = library_dirs
        self.process = None

    def execute(self, on_event, on_log) -> dict:
        trace_path = self.workspace / "native_events.jsonl"
        log_path = self.workspace / "native.log"
        env = os.environ.copy()
        env["ORB_EVALUATION_TRACE"] = str(trace_path)
        env["ORB_EVALUATION_TIMESTAMPS"] = str(self.workspace / "stereo_timestamps.txt")
        if self.library_dirs:
            env["LD_LIBRARY_PATH"] = os.pathsep.join(map(str, self.library_dirs)) + os.pathsep + env.get("LD_LIBRARY_PATH", "")
        count, ready, finished, pending, offset, log_offset = 0, False, False, b"", 0, 0
        attempts, seen_attempts = {}, set()
        selected, returned, filter_passed, bow_attempts = [{"loop": 0, "map_merge": 0} for _ in range(4)]
        started = time.monotonic()

        def drain():
            nonlocal count, ready, finished, pending, offset, log_offset
            if trace_path.exists():
                with trace_path.open("rb") as stream:
                    stream.seek(offset)
                    chunk = stream.read()
                    offset += len(chunk)
                pending += chunk
                while b"\n" in pending:
                    line, pending = pending.split(b"\n", 1)
                    if len(line) > 1_048_576:
                        raise ValueError("Native trace record exceeds 1 MiB")
                    event = json.loads(line, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
                    if not isinstance(event, dict) or type(event.get("schema_version")) is not int or event["schema_version"] != 1 or type(event.get("event_number")) is not int or event["event_number"] != count + 1:
                        raise ValueError("Invalid native trace schema or event order")
                    kind, payload = event.get("event_type"), event.get("payload")
                    stamp = event.get("dataset_timestamp_ns")
                    if kind not in EVENTS or not isinstance(payload, dict) or (stamp is not None and type(stamp) is not int):
                        raise ValueError("Invalid native measurement")
                    if finished:
                        raise ValueError("Native event after native_finished")
                    if count == 0:
                        if kind != "instrumentation_ready" or payload.get("revision") != self.revision or payload.get("instrumentation_version") != 6 or payload.get("sensor") != "stereo_imu":
                            raise ValueError("Missing or incompatible native instrumentation handshake")
                        ready = True
                    elif kind == "instrumentation_ready":
                        raise ValueError("Duplicate instrumentation handshake")
                    if kind in {"loop_verified", "map_merge_verified"} and type(payload.get("accepted")) is not bool:
                        raise ValueError("Verification result must have explicit accepted boolean")
                    if kind.endswith(("_proposed", "_verified")):
                        attempt_id = payload.get("attempt_id")
                        family = kind.rsplit("_", 1)[0]
                        if type(attempt_id) is not int or attempt_id < 1:
                            raise ValueError("Native attempt ID must be a positive integer")
                        if kind.endswith("_proposed"):
                            if attempt_id in seen_attempts:
                                raise ValueError("Duplicate native attempt ID")
                            attempts[attempt_id] = (family, tuple(payload.get(name) for name in
                                ("query_keyframe_id", "historical_keyframe_id", "query_timestamp_ns", "historical_timestamp_ns", "stage")))
                            seen_attempts.add(attempt_id)
                        elif attempts.pop(attempt_id, None) != (family, tuple(payload.get(name) for name in
                                ("query_keyframe_id", "historical_keyframe_id", "query_timestamp_ns", "historical_timestamp_ns", "stage"))):
                            raise ValueError("Verification does not match an outstanding proposal")
                    if kind == "timing":
                        seconds = payload.get("seconds")
                        if type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds < 0 or not isinstance(payload.get("operation"), str):
                            raise ValueError("Invalid native timing measurement")
                    if kind == "native_finished" and attempts:
                        raise ValueError("Native run finished with unverified proposals")
                    if kind == "loop_retrieval":
                        returned["loop"] += payload["loop_candidates"]
                        returned["map_merge"] += payload["merge_candidates"]
                    if kind == "loop_candidate":
                        family = payload["candidate_kind"]
                        if payload["selection_stage"] == "top_k" and payload["selection_reason"] == "selected":
                            selected[family] += 1
                        if payload["selection_stage"] == "geometry_filter" and payload["selection_reason"] == "passed":
                            filter_passed[family] += 1
                    if kind.endswith("_proposed") and payload["stage"] == "bow_geometry":
                        bow_attempts[kind.rsplit("_", 1)[0]] += 1
                    count += 1
                    finished = kind == "native_finished"
                    on_event(kind, {**payload, "native_event_number": count}, stamp)
                if len(pending) > 1_048_576:
                    raise ValueError("Native trace record exceeds 1 MiB")
            with log_path.open("rb") as stream:
                stream.seek(log_offset)
                chunk = stream.read(65536)
                log_offset += len(chunk)
            if chunk:
                on_log(chunk.decode("utf-8", errors="replace"))

        with log_path.open("xb") as log:
            # Inherit the adapter's process group so orchestrator cancellation covers native threads/children.
            self.process = subprocess.Popen(self.command, cwd=self.workspace, env=env,
                                            stdout=log, stderr=subprocess.STDOUT, shell=False)
            try:
                while self.process.poll() is None:
                    drain()
                    time.sleep(0.05)
                while log_offset < log_path.stat().st_size:
                    drain()
                drain()
                if self.process.returncode != 0:
                    raise RuntimeError(f"ORB-SLAM3 exited with code {self.process.returncode}; see {log_path}")
                if pending:
                    raise ValueError("Truncated native trace record")
                if not ready or not finished:
                    raise ValueError("Native trace is missing instrumentation_ready or native_finished")
                if selected != returned or filter_passed != bow_attempts:
                    raise ValueError(f"Native candidate census mismatch: selected={selected}, returned={returned}, filter_passed={filter_passed}, attempts={bow_attempts}")
                trajectories = [self.workspace / name for name in ("f_evaluation.txt", "kf_evaluation.txt")]
                if any(not path.is_file() or path.stat().st_size == 0 for path in trajectories):
                    raise ValueError("ORB-SLAM3 did not produce nonempty trajectories")
                return {"native_exit_code": self.process.returncode, "native_seconds": time.monotonic() - started,
                        "native_event_count": count, "trace": str(trace_path), "native_log": str(log_path),
                        "trajectories": [str(path) for path in trajectories],
                        "candidate_census": {"selected": selected, "returned": returned,
                                             "geometry_passed": filter_passed, "bow_attempts": bow_attempts, "consistent": True}}
            finally:
                self.close()

    def close(self):
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
