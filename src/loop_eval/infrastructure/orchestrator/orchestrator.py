"""Initialize evaluation and supervise benchmark adapter subprocesses."""

import math
import os
import platform
import re
import subprocess
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

import yaml

from loop_eval.infrastructure.evaluation_file_handler.handler import EvaluationFileHandler
from loop_eval.infrastructure.events import decode_event
from loop_eval.infrastructure.orchestrator.process_group import ProcessGroup
from loop_eval.paths import configuration_path, project_root


class EvaluationRunError(RuntimeError):
    def __init__(self, report_path: Path):
        self.report_path = report_path
        super().__init__(f"Evaluation contains failed cases. Report: {report_path}")


@dataclass
class ProcessState:
    spec: dict
    process: subprocess.Popen
    started: float
    group: ProcessGroup
    readers: list[threading.Thread] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    terminal: str | None = None


class Orchestrator:
    """Own processes; delegate all output writing to the file handler."""

    def __init__(self, config_path: Path | None = None) -> None:
        self.project_root = project_root()
        self.config_path = (
            Path(config_path)
            if config_path is not None
            else configuration_path("configs/runtime/benchmarks.yaml")
        )
        self._stop_requested = threading.Event()

    def stop(self) -> None:
        self._stop_requested.set()

    def _path(self, value: str) -> Path:
        path = Path(value)
        return (path if path.is_absolute() else self.project_root / path).resolve()

    def _load_config(self) -> dict:
        with self.config_path.open(encoding="utf-8") as stream:
            config = yaml.safe_load(stream)
        if not isinstance(config, dict) or config.get("version") != 1:
            raise ValueError("Configuration must be an object with version: 1")
        benchmarks = config.get("benchmarks")
        if not isinstance(benchmarks, list) or not benchmarks:
            raise ValueError(
                "Configure at least one benchmark adapter command before running evaluation"
            )
        run = config.setdefault("run", {})
        output = config.setdefault("output", {})
        dataset = config.setdefault("dataset", {})
        if not all(isinstance(section, dict) for section in (run, output, dataset)):
            raise ValueError("run, output, and dataset must be objects")
        run.setdefault("timezone", "Asia/Jerusalem")
        run.setdefault("max_parallel", 1)
        run.setdefault("seed", 0)
        if type(run["max_parallel"]) is not int or run["max_parallel"] < 1:
            raise ValueError("max_parallel must be a positive integer")
        if type(run["seed"]) is not int:
            raise ValueError("seed must be an integer")
        ZoneInfo(run["timezone"])
        output.setdefault("root", "evaluation/output")
        output.setdefault("queue_capacity", 1024)
        if type(output["queue_capacity"]) is not int or output["queue_capacity"] < 1:
            raise ValueError("queue_capacity must be a positive integer")
        dataset.setdefault("root", "evaluation/datasets/euroc")
        if not self._path(dataset["root"]).is_dir():
            raise ValueError("Dataset root does not exist")
        ids = set()
        for spec in benchmarks:
            if not isinstance(spec, dict):
                raise ValueError("Each benchmark must be an object")
            identifier = spec.get("id")
            if (
                not isinstance(identifier, str)
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", identifier)
                or identifier in ids
            ):
                raise ValueError(
                    "Benchmark IDs must be unique and use letters, digits, underscores, or hyphens"
                )
            ids.add(identifier)
            command = spec.get("command")
            if (
                not isinstance(command, list)
                or not command
                or not all(isinstance(arg, str) for arg in command)
                or not command[0]
            ):
                raise ValueError(f"{identifier}: command must be a nonempty list of strings")
            spec.setdefault("cwd", ".")
            if not self._path(spec["cwd"]).is_dir():
                raise ValueError(f"{identifier}: working directory does not exist")
            spec.setdefault("timeout_seconds", 600)
            timeout = spec["timeout_seconds"]
            if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
                raise ValueError(f"{identifier}: timeout_seconds must be positive and finite")
        return config

    def _read_stdout(
        self, state: ProcessState, handler: EvaluationFileHandler, run_id: str
    ) -> None:
        number = 1
        try:
            with state.process.stdout as stream:
                while line := stream.readline(1_048_577):
                    if len(line) > 1_048_576:
                        raise ValueError("Event exceeds the 1 MiB character limit")
                    if state.terminal is not None:
                        raise ValueError("Received an event after a terminal event")
                    event = decode_event(line, run_id, state.spec["id"], number)
                    handler.enqueue(state.spec["id"], event)
                    number += 1
                    if event["event_type"] in {"completed", "failed"}:
                        state.terminal = event["event_type"]
        except Exception as error:
            state.errors.append(f"stdout: {error}")

    def _read_stderr(self, state: ProcessState, handler: EvaluationFileHandler) -> None:
        try:
            with state.process.stderr as stream:
                while text := stream.read(8192):
                    handler.log(state.spec["id"], text)
        except Exception as error:
            state.errors.append(f"stderr: {error}")

    def _start(
        self, spec: dict, handler: EvaluationFileHandler, run_id: str, config: dict
    ) -> ProcessState:
        substitutions = {
            "{python}": sys.executable,
            "{project_root}": str(self.project_root),
            "{dataset_root}": str(self._path(config["dataset"]["root"])),
        }
        command = []
        for argument in spec["command"]:
            for token, value in substitutions.items():
                argument = argument.replace(token, value)
            command.append(argument)
        env = os.environ.copy()
        env.update(
            {
                "EVALUATION_RUN_ID": run_id,
                "EVALUATION_BENCHMARK_ID": spec["id"],
                "EVALUATION_DATASET_ROOT": substitutions["{dataset_root}"],
                "EVALUATION_SEED": str(config["run"]["seed"]),
                "PYTHONUNBUFFERED": "1",
            }
        )
        env["PYTHONPATH"] = str(self.project_root / "src") + os.pathsep + env.get("PYTHONPATH", "")
        kwargs = (
            {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW}
            if os.name == "nt"
            else {"start_new_session": True}
        )
        process = subprocess.Popen(
            command,
            cwd=self._path(spec["cwd"]),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            **kwargs,
        )
        try:
            group = ProcessGroup(process)
        except BaseException:
            process.kill()
            process.wait()
            process.stdout.close()
            process.stderr.close()
            raise
        state = ProcessState(spec, process, time.monotonic(), group)
        try:
            handler.record_status(spec["id"], status="running", pid=process.pid, command=command)
            state.readers = [
                threading.Thread(target=self._read_stdout, args=(state, handler, run_id)),
                threading.Thread(target=self._read_stderr, args=(state, handler)),
            ]
            for reader in state.readers:
                reader.start()
        except BaseException:
            group.terminate()
            process.wait()
            group.close()
            for reader in state.readers:
                if reader.ident is not None:
                    reader.join()
            process.stdout.close()
            process.stderr.close()
            raise
        return state

    @staticmethod
    def _terminate(state: ProcessState) -> None:
        state.group.terminate()
        if state.process.poll() is None:
            state.process.kill()
        state.process.wait(timeout=15)

    def _finish(self, state: ProcessState, handler: EvaluationFileHandler) -> bool:
        if state.group.close():
            state.errors.append("Benchmark left descendant processes running")
        for reader in state.readers:
            reader.join(timeout=5)
        if any(reader.is_alive() for reader in state.readers):
            state.errors.append("IPC pipes did not close; stopping descendant processes")
            self._terminate(state)
            for reader in state.readers:
                reader.join(timeout=5)
            if any(reader.is_alive() for reader in state.readers):
                raise RuntimeError("Benchmark IPC reader did not stop")
        if state.process.returncode != 0:
            state.errors.append(f"Process exited with code {state.process.returncode}")
        if state.terminal != "completed":
            state.errors.append(f"Expected completed event; received {state.terminal!r}")
        failed = bool(state.errors)
        handler.record_status(
            state.spec["id"],
            status="failed" if failed else "complete",
            exit_code=state.process.returncode,
            errors=state.errors,
            execution_seconds=time.monotonic() - state.started,
        )
        return failed

    def run(self) -> Path:
        config = self._load_config()
        self._stop_requested.clear()
        started = datetime.now(ZoneInfo(config["run"]["timezone"]))
        run_id = uuid4().hex
        name = f"evaluation_{started:%Y-%m-%d_%H-%M-%S_%f}_{run_id[:8]}.json"
        report_path = self._path(config["output"]["root"]) / name
        handler = EvaluationFileHandler(
            report_path,
            {
                "run_id": run_id,
                "started_at": started.isoformat(),
                "started_at_utc": started.astimezone(UTC).isoformat(),
                "timezone": config["run"]["timezone"],
                "config": config,
                "environment": {"python": sys.version, "platform": platform.platform()},
            },
            [spec["id"] for spec in config["benchmarks"]],
            config["output"]["queue_capacity"],
        )
        pending, active = deque(config["benchmarks"]), []
        failures, successes, abort_error = 0, 0, None
        try:
            while pending or active:
                handler.check()
                if self._stop_requested.is_set():
                    raise InterruptedError("Evaluation stopped")
                while pending and len(active) < config["run"]["max_parallel"]:
                    spec = pending.popleft()
                    try:
                        active.append(self._start(spec, handler, run_id, config))
                    except OSError as error:
                        failures += 1
                        handler.record_status(spec["id"], status="failed", errors=[str(error)])
                for state in active[:]:
                    if state.process.poll() is None:
                        if time.monotonic() - state.started >= state.spec["timeout_seconds"]:
                            state.errors.append("Benchmark exceeded timeout_seconds")
                            self._terminate(state)
                        elif state.errors:
                            self._terminate(state)
                    if state.process.poll() is not None:
                        if self._finish(state, handler):
                            failures += 1
                        else:
                            successes += 1
                        active.remove(state)
                time.sleep(0.02)
        except BaseException as error:
            abort_error = error
            for state in active:
                self._terminate(state)
                state.group.close()
                for reader in state.readers:
                    reader.join(timeout=5)
                try:
                    handler.record_status(state.spec["id"], status="cancelled", errors=[str(error)])
                except RuntimeError:
                    pass
            for spec in pending:
                try:
                    handler.record_status(spec["id"], status="cancelled", errors=[str(error)])
                except RuntimeError:
                    pass
        finally:
            status = (
                "failed"
                if abort_error or (failures and not successes)
                else "partial"
                if failures
                else "complete"
            )
            handler.close(status, str(abort_error) if abort_error else None)
        print(f"Evaluation {status}: {report_path}")
        if abort_error:
            raise abort_error
        if failures:
            raise EvaluationRunError(report_path)
        return report_path
