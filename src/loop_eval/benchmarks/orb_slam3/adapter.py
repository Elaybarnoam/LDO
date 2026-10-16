"""ORB-specific hooks; Benchmark owns lifecycle and publisher interaction."""

import hashlib
import json
import os
import re
import shutil
from pathlib import Path
from uuid import uuid4

import yaml

from loop_eval.benchmarks.base import Benchmark
from loop_eval.benchmarks.loop_events import PAIR_EVENTS, QUERY_EVENTS
from loop_eval.paths import project_root

from .euroc_input import prepare
from .native_session import NativeSession


class ORBSLAM3Benchmark(Benchmark):
    def __init__(self, config_path: Path, publisher=None):
        super().__init__(publisher=publisher)
        self.config_path = config_path.resolve()
        self.project_root = project_root()
        self.session = None
        self.workspace = None
        self.artifact_path = None
        self._exported = False

    def _path(self, value):
        path = Path(value)
        return (path if path.is_absolute() else self.project_root / path).resolve()

    def setup(self):
        if os.name != "posix":
            raise RuntimeError(
                "Run the complete evaluation pipeline inside WSL/Linux; see setup/README.md"
            )
        with self.config_path.open(encoding="utf-8") as stream:
            config = yaml.safe_load(stream)
        if not isinstance(config, dict) or config.get("version") != 1:
            raise ValueError("ORB config requires version: 1")
        self.sequence_id = config["sequence"]
        self.validate_revisits = config.get("diagnostics", {}).get("validate_revisit", False)
        if not isinstance(self.sequence_id, str) or not re.fullmatch(
            r"(?:MH|V[12])_\d{2}_(?:easy|medium|difficult)", self.sequence_id
        ):
            raise ValueError("Invalid EuRoC sequence name")
        native = config["native"]
        binary, vocabulary, settings, manifest = [
            self._path(native[key]) for key in ("binary", "vocabulary", "settings", "manifest")
        ]
        for path in (binary, vocabulary, settings, manifest):
            if not path.is_file():
                raise ValueError(
                    f"Missing native installation file: {path}; run setup/build.py in Linux"
                )
        lock = json.loads(Path(__file__).with_name("upstream.lock.json").read_text())
        provenance = json.loads(manifest.read_text())
        if (
            provenance.get("revision") != lock["orb_slam3"]["revision"]
            or provenance.get("instrumentation_version") != lock["instrumentation_version"]
        ):
            raise ValueError("Native build manifest does not match pinned source/instrumentation")

        def digest(path):
            checksum = hashlib.sha256()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    checksum.update(chunk)
            return checksum.hexdigest()

        if (
            digest(binary) != provenance["binary_sha256"]
            or digest(settings) != provenance["settings_sha256"]
        ):
            raise ValueError("Native binary/settings differ from build manifest")
        artifacts = provenance.get("artifacts")
        if not isinstance(artifacts, dict) or str(vocabulary) not in artifacts:
            raise ValueError("Native build manifest is missing artifact checksums")
        for name, expected in artifacts.items():
            path = Path(name)
            if not path.is_file() or digest(path) != expected:
                raise ValueError(f"Native artifact differs from build manifest: {path}")
        self.workspace = (
            self._path(config["workspace_root"])
            / f"{os.environ.get('EVALUATION_RUN_ID', 'local')}_{uuid4().hex}"
        )
        self.artifact_path = (
            self._path(config.get("artifact_root", "evaluation/output/native/orb_slam3"))
            / self.workspace.name
        )
        self.workspace.mkdir(parents=True, exist_ok=False)
        (self.workspace / "build_manifest.json").write_text(json.dumps(provenance, indent=2))
        dataset_root = self._path(os.environ.get("EVALUATION_DATASET_ROOT", config["dataset_root"]))
        native_dataset_root = self._path(config.get("native_dataset_root", str(dataset_root)))
        cache = None
        if native_dataset_root != dataset_root:
            cache_manifest = native_dataset_root / self.sequence_id / "cache_manifest.json"
            if not cache_manifest.is_file():
                raise ValueError("Stage this sequence in Linux first with setup/stage_euroc.py")
            cache = json.loads(cache_manifest.read_text())
            source_archive = json.loads(
                (dataset_root / "_archives" / f"{self.sequence_id}.json").read_text()
            )
            if (
                cache.get("source_sequence") != str(dataset_root / self.sequence_id)
                or cache.get("archive_sha256") != source_archive["sha256"]
            ):
                raise ValueError("Dataset cache does not match installed source archive")
        self.inputs = prepare(native_dataset_root / self.sequence_id, self.workspace)
        command = [
            str(binary),
            str(vocabulary),
            str(settings),
            str(self.inputs.sequence_path),
            str(self.inputs.timestamps_path),
            "evaluation",
        ]
        library_dirs = [self._path(value) for value in native.get("library_dirs", [])]
        if any(not path.is_dir() for path in library_dirs):
            raise ValueError("Native library directory does not exist")
        self.session = NativeSession(command, self.workspace, provenance["revision"], library_dirs)
        self.publish(
            "input_prepared",
            {
                "frames": self.inputs.frame_count,
                "imu_samples": self.inputs.imu_count,
                "unpaired_camera_frames": self.inputs.unpaired_camera_frames,
                "source_sequence": str(dataset_root / self.sequence_id),
                "native_sequence": str(self.inputs.sequence_path),
                "dataset_cache": cache,
                "workspace": str(self.workspace),
                "provenance": provenance,
            },
        )

    def execute(self):
        result = self.session.execute(self._publish_native, self.log)
        if self.validate_revisits:
            from .diagnostics.revisit import validate_revisit

            validation = validate_revisit(
                self.workspace / "native_events.jsonl", self.inputs.sequence_path, self.workspace
            )
            for prefix in ("query", "historical"):
                if f"{prefix}_image" in validation:
                    validation[f"{prefix}_image"] = str(
                        self.artifact_path / validation[f"{prefix}_image"]
                    )
            self.publish("revisit_validation", validation)
        self._export_artifacts()
        result["native_workspace"] = str(self.workspace)
        result["trace"] = str(self.artifact_path / "native_events.jsonl")
        result["native_log"] = str(self.artifact_path / "native.log")
        result["trajectories"] = [
            str(self.artifact_path / Path(path).name) for path in result["trajectories"]
        ]
        return result

    def _publish_native(self, event_type, payload, timestamp_ns):
        if event_type in PAIR_EVENTS | QUERY_EVENTS:
            self.publish_loop_measurement(event_type, payload, "orb_slam3_dbow2", timestamp_ns)
        else:
            self.publish(event_type, payload, timestamp_ns)

    def _export_artifacts(self):
        if self._exported or self.workspace is None or not self.workspace.exists():
            return
        self.artifact_path.mkdir(parents=True, exist_ok=False)
        for name in (
            "build_manifest.json",
            "stereo_timestamps.txt",
            "native_events.jsonl",
            "native.log",
            "f_evaluation.txt",
            "kf_evaluation.txt",
            "revisit_validation.json",
            "revisit_query_cam0.png",
            "revisit_historical_cam0.png",
        ):
            source = self.workspace / name
            if source.is_file():
                shutil.copyfile(source, self.artifact_path / name)
        self._exported = True
        self.publish(
            "native_artifacts",
            {"directory": str(self.artifact_path), "native_workspace": str(self.workspace)},
        )

    def cleanup(self):
        if self.session is not None:
            self.session.close()
        self._export_artifacts()
