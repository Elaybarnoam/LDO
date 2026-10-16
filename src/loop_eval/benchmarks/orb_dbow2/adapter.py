"""Benchmark lifecycle around standalone native chronological retrieval."""

import json
import os
import subprocess
import time
from pathlib import Path
from uuid import uuid4

import yaml

from loop_eval.benchmarks.base import Benchmark
from loop_eval.paths import project_root

from .build import digest
from .replay import make_replay


class ORBDBoW2Benchmark(Benchmark):
    def __init__(self, config_path, publisher=None):
        super().__init__(publisher=publisher)
        self.config_path = Path(config_path)
        self.root = project_root()
        self.process = None

    def setup(self):
        if os.name != "posix":
            raise RuntimeError("Run evaluation inside WSL with evaluation/run_wsl.py")
        self.config = yaml.safe_load(self.config_path.read_text())
        if self.config.get("version") != 1:
            raise ValueError("Unsupported retrieval config version")
        self.sequence_id = self.config["sequence"]
        if Path(self.sequence_id).name != self.sequence_id:
            raise ValueError("Invalid sequence name")
        self.top_k = self.config["top_k"]
        if type(self.top_k) is not int or not 1 <= self.top_k <= 100:
            raise ValueError("top_k must be an integer in [1, 100]")
        exclusion = self.config["temporal_exclusion_seconds"]
        if type(exclusion) not in (float, int) or not 0 < exclusion <= 3600:
            raise ValueError("Invalid temporal exclusion")
        self.exclusion_ns = round(exclusion * 1_000_000_000)
        source = Path(self.config["native"]["source_root"])
        build = Path(self.config["native"]["build_root"])
        self.binary = build / "orb_dbow2"
        self.vocabulary = source / "Vocabulary/ORBvoc.txt"
        self.settings = source / "Examples/Stereo-Inertial/EuRoC.yaml"
        manifest = json.loads((build / "manifest.json").read_text())
        lock = json.loads(
            (Path(__file__).parent.parent / "orb_slam3/upstream.lock.json").read_text()
        )["orb_slam3"]
        if manifest["upstream"] != lock:
            raise ValueError("Retrieval build is not from pinned upstream")
        if manifest.get("verification", {}).get("passed") is not True or manifest[
            "verification"
        ].get("binary_sha256") != digest(self.binary):
            raise ValueError("Native retrieval build has not passed upstream parity verification")
        for name, expected in manifest["artifacts"].items():
            if digest(name) != expected:
                raise ValueError(f"Retrieval build/input changed: {name}; rebuild first")
        for path in (self.binary, self.vocabulary, self.settings):
            if str(path) not in manifest["artifacts"]:
                raise ValueError(f"Unverified native path: {path}")
        dataset = Path(os.environ.get("EVALUATION_DATASET_ROOT", self.config["dataset_root"]))
        if not dataset.is_absolute():
            dataset = self.root / dataset
        sequence = Path(self.config["native_dataset_root"]) / self.sequence_id
        self.sequence_path = sequence
        cache = json.loads((sequence / "cache_manifest.json").read_text())
        archive = json.loads((dataset / "_archives" / f"{self.sequence_id}.json").read_text())
        if (
            cache["source_sequence"] != str(dataset / self.sequence_id)
            or cache["archive_sha256"] != archive["sha256"]
        ):
            raise ValueError("Native dataset cache does not match installed dataset")
        self.replay = make_replay(sequence, self.config["sample_hz"])
        self.artifacts = (
            self.root
            / "evaluation/output/native/orb_dbow2"
            / f"{os.environ.get('EVALUATION_RUN_ID', 'local')}_{uuid4().hex}"
        )
        self.artifacts.mkdir(parents=True, exist_ok=False)
        self.index = self.artifacts / "replay.tsv"
        self.index.write_text("".join(f"{stamp}\t{image}\n" for stamp, image in self.replay))
        (self.artifacts / "build_manifest.json").write_text(json.dumps(manifest, indent=2))
        (self.artifacts / "verification.json").write_text(
            json.dumps(manifest["verification"], indent=2)
        )
        policy = {
            "benchmark_type": "image_retrieval",
            "detector_id": "orb_dbow2",
            "camera": "cam0",
            "sample_hz": self.config["sample_hz"],
            "temporal_exclusion_seconds": exclusion,
            "top_k": self.top_k,
            "sample_count": len(self.replay),
            "query_before_insert": True,
            "ranking": "All eligible history scored by vocabulary.score; positive scores only; ties oldest first",
            "imu_usage": "None in retrieval; dataset includes synchronized IMU",
            "full_slam": False,
            "provenance": manifest["upstream"],
            "upstream_parity_check": manifest["verification"],
            "artifacts": str(self.artifacts),
            "replay_sha256": digest(self.index),
            "dataset_cache": cache,
        }
        self.publish("retrieval_setup", policy)

    def execute(self):
        started = time.monotonic()
        command = [
            str(self.binary),
            str(self.vocabulary),
            str(self.settings),
            str(self.index),
            str(self.exclusion_ns),
            str(self.top_k),
        ]
        feature_root = self.artifacts / "orb_features"
        feature_root.mkdir()
        env = dict(os.environ, LDO_ORB_FEATURE_DIR=str(feature_root))
        count = 0
        eligible_cursor = 0
        with (
            (self.artifacts / "native.stderr.log").open("w") as errors,
            (self.artifacts / "retrieval.jsonl").open("w") as trace,
        ):
            # Inherit the orchestrator's process group for cancellation/timeout.
            self.process = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=errors, text=True, env=env
            )
            for line in self.process.stdout:
                if len(line) > 1_048_576:
                    raise ValueError("Native retrieval record too large")
                payload = json.loads(line)
                if (
                    count >= len(self.replay)
                    or payload["query_timestamp_ns"] != self.replay[count][0]
                ):
                    raise ValueError("Native replay count/order differs from input")
                stamp = self.replay[count][0]
                while (
                    eligible_cursor < count
                    and self.replay[eligible_cursor][0] <= stamp - self.exclusion_ns
                ):
                    eligible_cursor += 1
                if (
                    payload["eligible_history_count"] != eligible_cursor
                    or len(payload["candidates"]) > self.top_k
                ):
                    raise ValueError("Native eligibility/count differs from policy")
                eligible_stamps = {item[0] for item in self.replay[:eligible_cursor]}
                if any(
                    item["historical_timestamp_ns"] not in eligible_stamps
                    for item in payload["candidates"]
                ):
                    raise ValueError("Native candidate outside eligible history")
                self.publish_retrieval(payload, "orb_dbow2", stamp)
                trace.write(line)
                trace.flush()
                count += 1
            code = self.process.wait()
            if code != 0:
                raise RuntimeError(
                    f"Native retrieval exited {code}: {(self.artifacts / 'native.stderr.log').read_text()[-4000:]}"
                )
        if count != len(self.replay):
            raise ValueError("Native replay was truncated")
        exports = {}
        for stamp, left_path in self.replay:
            for camera in ("cam0", "cam1"):
                image_path = self.sequence_path / "mav0" / camera / "data" / Path(left_path).name
                export = feature_root / f"{stamp}_{camera}.orb"
                exports[export.name] = {
                    "sha256": digest(export),
                    "image_sha256": digest(image_path),
                }
        (feature_root / "manifest.json").write_text(
            json.dumps(
                {
                    "source": "upstream_ORB_SLAM3_ORBextractor",
                    "coordinates": "raw_sensor_pixels_via_rectification_maps",
                    "exports": exports,
                },
                indent=2,
            )
            + "\n"
        )
        native_seconds = time.monotonic() - started
        if self.sequence_id == "MH_01_easy":
            query = min(self.replay, key=lambda row: abs(row[0] - 1403636760513555456))[0]
            historical = min(self.replay, key=lambda row: abs(row[0] - 1403636599813555456))[0]
            with (self.artifacts / "retrieval.jsonl").open() as stream:
                record = next(
                    json.loads(line)
                    for line in stream
                    if json.loads(line)["query_timestamp_ns"] == query
                )
            rank = next(
                (
                    candidate["rank"]
                    for candidate in record["candidates"]
                    if candidate["historical_timestamp_ns"] == historical
                ),
                None,
            )
            self.publish(
                "retrieval_diagnostic",
                {
                    "description": "Nearest uniform replay samples to the visually inspected revisit from the earlier full-SLAM investigation. Original pair had strong image overlap; these sampled images have not been independently labeled.",
                    "query_timestamp_ns": query,
                    "historical_timestamp_ns": historical,
                    "target_rank": rank,
                    "candidates": record["candidates"],
                },
                query,
            )
        checker = self.config.get("candidate_evaluation", {})
        checking = None
        if checker.get("enabled", False):
            config_path = Path(checker["config"])
            if not config_path.is_absolute():
                config_path = self.root / config_path
            checking = self.evaluate_candidates(
                self.sequence_path,
                self.index,
                self.artifacts / "retrieval.jsonl",
                self.artifacts / "candidate_checks",
                config_path,
                feature_root=feature_root,
            )
        return {
            "benchmark_type": "image_retrieval",
            "native_exit_code": code,
            "native_seconds": native_seconds,
            "candidate_evaluation": checking,
            "query_count": count,
            "trace": str(self.artifacts / "retrieval.jsonl"),
            "artifacts": str(self.artifacts),
        }

    def cleanup(self):
        if self.process is not None:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
            if self.process.stdout:
                self.process.stdout.close()
