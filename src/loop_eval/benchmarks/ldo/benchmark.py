"""Pretrained LDO replay and unchanged offline stereo/XYZ evaluation."""

import json
import os
import shutil
import time
from pathlib import Path
from uuid import uuid4

import yaml

from ldo.artifacts import identity, sha256, write_json
from ldo.configuration import build_detector, load_config
from ldo.contracts import KeyframeInput
from ldo.evidence import EvidenceWriter
from loop_eval.benchmarks.base import Benchmark
from loop_eval.benchmarks.orb_dbow2.replay import make_replay
from loop_eval.paths import project_root
from loop_eval.tasks.feature_matching.xyz.learned_features import SavedCorrespondences


class LDOBenchmark(Benchmark):
    def __init__(self, config_path: Path, publisher=None) -> None:
        super().__init__(publisher=publisher)
        self.config_path = config_path.resolve()
        self.root = project_root()
        self.detector = None

    def _path(self, value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else self.root / path

    def setup(self) -> None:
        self.config = yaml.safe_load(self.config_path.read_text(encoding="utf-8"))
        expected = {
            "version",
            "sequence",
            "dataset_root",
            "native_dataset_root",
            "sample_hz",
            "detector_config",
            "candidate_evaluation",
        }
        if (
            not isinstance(self.config, dict)
            or set(self.config) != expected
            or self.config["version"] != 1
        ):
            raise ValueError("Invalid LDO benchmark configuration")
        self.sequence_id = self.config["sequence"]
        if not isinstance(self.sequence_id, str) or Path(self.sequence_id).name != self.sequence_id:
            raise ValueError("Invalid sequence name")
        dataset = self._path(os.environ.get("EVALUATION_DATASET_ROOT", self.config["dataset_root"]))
        self.sequence_path = Path(self.config["native_dataset_root"]) / self.sequence_id
        cache = json.loads((self.sequence_path / "cache_manifest.json").read_text())
        archive = json.loads((dataset / "_archives" / f"{self.sequence_id}.json").read_text())
        if (
            cache["source_sequence"] != str(dataset / self.sequence_id)
            or cache["archive_sha256"] != archive["sha256"]
        ):
            raise ValueError("Native dataset cache differs from the installed dataset")
        detector_path = self._path(self.config["detector_config"])
        self.detector_config = load_config(detector_path)
        if self.detector_config.seed != int(
            os.environ.get("EVALUATION_SEED", self.detector_config.seed)
        ):
            raise ValueError("Runner and model configuration seeds must agree")
        self.replay = make_replay(self.sequence_path, self.config["sample_hz"])
        self.artifacts = (
            self.root
            / "evaluation/output/native/ldo"
            / f"{os.environ.get('EVALUATION_RUN_ID', 'local')}_{uuid4().hex}"
        )
        self.artifacts.mkdir(parents=True, exist_ok=False)
        self.index_path = self.artifacts / "replay.tsv"
        self.index_path.write_text(
            "".join(f"{stamp}\t{image}\n" for stamp, image in self.replay), encoding="utf-8"
        )
        self.detector, self.manifest = build_detector(self.detector_config)
        self.manifest["code_sha256"] = {
            str(path.relative_to(self.root)): sha256(path)
            for path in sorted((self.root / "src/ldo").rglob("*.py"))
        }
        self.manifest["configuration_sha256"] = {
            str(path): sha256(path) for path in (detector_path, self.config_path)
        }
        # Archive the code/configuration that defines this experiment, not only
        # hashes pointing at a mutable working directory.
        snapshot = self.artifacts / "source"
        code_files = list((self.root / "src/ldo").rglob("*.py"))
        code_files += list((self.root / "src/loop_eval").rglob("*.py"))
        code_files += [
            detector_path,
            self.config_path,
            self.root / "pyproject.toml",
            self.root / "uv.lock",
        ]
        for path in code_files:
            path = path.resolve()
            relative = (
                path.relative_to(self.root)
                if path.is_relative_to(self.root)
                else Path("external_configuration") / f"{sha256(path)[:12]}_{path.name}"
            )
            destination = snapshot / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)
        self.manifest["snapshot_sha256"] = {
            str(path.relative_to(snapshot)): sha256(path)
            for path in sorted(snapshot.rglob("*"))
            if path.is_file()
        }
        self.manifest.pop("manifest_id")
        self.manifest["manifest_id"] = identity(self.manifest)
        write_json(self.artifacts / "model_manifest.json", self.manifest)
        self.publish(
            "retrieval_setup",
            {
                "benchmark_type": "image_retrieval",
                "detector_id": self.detector_config.variant,
                "camera": "cam0",
                "sample_hz": self.config["sample_hz"],
                "temporal_exclusion_seconds": self.detector_config.exclusion_ns / 1e9,
                "top_k": self.detector_config.top_k,
                "sample_count": len(self.replay),
                "query_before_insert": True,
                "ranking": "Exact normalized cosine over eligible history; ties oldest first; local evidence preserves retrieval order",
                "score_definition": "cosine_similarity",
                "imu_usage": "None in detector; existing estimator retains IMU",
                "full_slam": False,
                "provenance": {
                    "revision": self.manifest["installation"]["pins"]["megaloc"]["revision"]
                },
                "model_manifest": self.manifest,
                "artifacts": str(self.artifacts),
                "replay_sha256": sha256(self.index_path),
                "dataset_cache": cache,
            },
        )

    def execute(self) -> dict:
        import torch

        if self.detector is None:
            raise RuntimeError("LDO was not initialized")
        if self.detector_config.device == "cuda":
            torch.cuda.reset_peak_memory_stats()
        started = time.perf_counter()
        evidence_root = self.artifacts / "learned_features"
        writer = EvidenceWriter(evidence_root, self.manifest)
        query_timings = []
        trace_path = self.artifacts / "retrieval.jsonl"
        with trace_path.open("x", encoding="utf-8") as trace:
            for number, (stamp, image) in enumerate(self.replay, 1):
                batch = self.detector.process_keyframe(
                    KeyframeInput(str(stamp), stamp, image, self.sequence_id)
                )
                query_timings.append(batch.timings_ms["total"])
                writer.append(batch)
                payload = {
                    "query_timestamp_ns": stamp,
                    "eligible_history_count": batch.eligible_history_count,
                    "feature_count": len(batch.query_features.points),
                    "bow_word_count": 0,
                    "descriptor_dimension": self.detector.encoder.dimension,
                    "score_definition": "cosine_similarity",
                    "timings_ms": batch.timings_ms,
                    "candidates": [
                        {
                            "rank": c.rank,
                            "historical_timestamp_ns": c.historical.timestamp_ns,
                            "score": c.retrieval_score,
                            "reported_match_count": len(c.matches.indices),
                        }
                        for c in batch.candidates
                    ],
                }
                self.publish_retrieval(payload, self.detector_config.variant, stamp)
                trace.write(json.dumps(payload, allow_nan=False) + "\n")
                if number % 20 == 0:
                    self.log(f"LDO: {number}/{len(self.replay)} keyframes processed")
        writer.finalize()
        stats = {
            "inference_seconds": time.perf_counter() - started,
            "cache_hits": self.detector.cache.hits,
            "cache_misses": self.detector.cache.misses,
            "cached_feature_bytes": self.detector.cache.bytes_used,
            "descriptor_index_bytes": self.detector.index.bytes_used,
            "peak_gpu_bytes": torch.cuda.max_memory_allocated()
            if self.detector_config.device == "cuda"
            else 0,
        }
        import numpy as np

        stats["query_latency_ms"] = {
            "p50": float(np.percentile(query_timings, 50)),
            "p95": float(np.percentile(query_timings, 95)),
            "maximum": max(query_timings),
        }
        write_json(self.artifacts / "runtime.json", stats)
        self.detector.close()
        self.detector = None
        if self.detector_config.device == "cuda":
            torch.cuda.empty_cache()
        checker = self.config["candidate_evaluation"]
        checking = None
        if checker["enabled"]:
            self.log(
                "LDO inference complete; evaluating saved assignments with unchanged stereo/XYZ policy"
            )
            checking = self.evaluate_candidates(
                self.sequence_path,
                self.index_path,
                trace_path,
                self.artifacts / "candidate_checks",
                self._path(checker["config"]),
                feature_root=evidence_root,
                correspondence_source=SavedCorrespondences(evidence_root),
            )
        return {
            "benchmark_type": "image_retrieval",
            "native_exit_code": 0,
            "query_count": len(self.replay),
            "candidate_evaluation": checking,
            "trace": str(trace_path),
            "artifacts": str(self.artifacts),
            "runtime": stats,
            "model_manifest": str(self.artifacts / "model_manifest.json"),
        }

    def cleanup(self) -> None:
        if self.detector is not None:
            self.detector.close()
            self.detector = None
