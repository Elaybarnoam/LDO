"""Frozen detector adapters consume replay images only, never reference geometry."""

import json
import os
import re
import subprocess
from pathlib import Path

import cv2
import numpy as np
import yaml

from ldo.contracts import KeyframeInput
from ldo.evidence import EvidenceWriter
from tasks.feature_matching.xyz.orb_features import read_features
from tasks.loop_closure.comparison.reference import sha256, write_json


def native_settings(source, target):
    original = (source / "Examples/Stereo-Inertial/EuRoC.yaml").read_text()
    fields = {}
    for key in ("nFeatures", "scaleFactor", "nLevels", "iniThFAST", "minThFAST"):
        found = re.search(r"(?m)^ORBextractor\." + key + r":\s*([0-9.]+)", original)
        if found is None:
            raise ValueError("Pinned ORB extraction setting missing")
        fields[key] = found.group(1)
    text = '%YAML:1.0\nFile.version: "1.0"\nCamera.type: "PinHole"\nCamera.width: 640\nCamera.height: 640\n'
    for camera in ("Camera1", "Camera2"):
        for key, value in {
            "fx": 320.0,
            "fy": 320.0,
            "cx": 319.5,
            "cy": 319.5,
            "k1": 0.0,
            "k2": 0.0,
            "p1": 0.0,
            "p2": 0.0,
        }.items():
            text += f"{camera}.{key}: {value}\n"
    text += "Stereo.T_c1_c2: !!opencv-matrix\n   rows: 4\n   cols: 4\n   dt: f\n   data: [1., 0., 0., 0.25, 0., 1., 0., 0., 0., 0., 1., 0., 0., 0., 0., 1.]\n"
    text += "".join(f"ORBextractor.{key}: {value}\n" for key, value in fields.items())
    target.write_text(text)
    return fields


def validate_native(config_path):
    settings = yaml.safe_load(config_path.read_text())
    source, build = [Path(settings["native"][key]) for key in ("source_root", "build_root")]
    manifest = json.loads((build / "manifest.json").read_text())
    if manifest["verification"]["passed"] is not True:
        raise ValueError("Native ORB build lacks upstream parity verification")
    for name, expected in manifest["artifacts"].items():
        if sha256(Path(name)) != expected:
            raise ValueError(f"Pinned native artifact changed: {name}")
    return source, build, manifest


def run_orb(replay_root, output, source, build, protocol):
    output.mkdir(parents=True, exist_ok=False)
    exports = output / "orb_features"
    exports.mkdir()
    settings = output / "camera.yaml"
    parameters = native_settings(source, settings)
    trace = output / "retrieval.jsonl"
    with trace.open("x") as stdout, (output / "native.stderr.log").open("x") as stderr:
        subprocess.run(
            [
                str(build / "orb_dbow2"),
                str(source / "Vocabulary/ORBvoc.txt"),
                str(settings),
                str(replay_root / "replay.tsv"),
                str(protocol["exclusion_ns"]),
                str(protocol["top_k"]),
            ],
            env={**os.environ, "LDO_ORB_FEATURE_DIR": str(exports)},
            stdout=stdout,
            stderr=stderr,
            check=True,
            timeout=900,
        )
    manifest = {"source": "pinned_upstream_orb", "exports": {}, "settings": parameters}
    for line in (replay_root / "replay.tsv").read_text().splitlines():
        stamp, image = line.split("\t")
        for camera in ("cam0", "cam1"):
            name = f"{stamp}_{camera}.orb"
            path = Path(image.replace("/cam0/", f"/{camera}/"))
            manifest["exports"][name] = {
                "sha256": sha256(exports / name),
                "image_sha256": sha256(path),
            }
    write_json(exports / "manifest.json", manifest)
    return trace


def run_ldo(detector, model_manifest, replay_root, output):
    output.mkdir(parents=True, exist_ok=False)
    detector.reset()
    writer = EvidenceWriter(output / "learned_features", model_manifest)
    with (output / "retrieval.jsonl").open("x") as stream:
        for line in (replay_root / "replay.tsv").read_text().splitlines():
            stamp, image = line.split("\t")
            frame = KeyframeInput(stamp, int(stamp), Path(image), session_id=replay_root.name)
            batch = detector.process_keyframe(frame)
            writer.append(batch)
            stream.write(
                json.dumps(
                    {
                        "query_timestamp_ns": frame.timestamp_ns,
                        "eligible_history_count": batch.eligible_history_count,
                        "candidates": [
                            {
                                "rank": c.rank,
                                "historical_timestamp_ns": c.historical.timestamp_ns,
                                "score": c.retrieval_score,
                            }
                            for c in batch.candidates
                        ],
                        "timings_ms": batch.timings_ms,
                    }
                )
                + "\n"
            )
    writer.finalize()
    return output / "retrieval.jsonl"


class FeaturePairs:
    def __init__(self, root, method, images):
        self.root, self.method, self.images = root, method, images
        self.cache = {}
        self.manifest = json.loads(
            (
                root / ("orb_features" if method == "orb" else "learned_features") / "manifest.json"
            ).read_text()
        )
        self.matcher = cv2.BFMatcher(cv2.NORM_HAMMING)

    def features(self, stamp):
        if stamp not in self.cache:
            if self.method == "orb":
                points, descriptors, _ = read_features(
                    self.root / "orb_features", self.images[stamp]
                )
            else:
                path = self.root / "learned_features" / f"{stamp}_cam0.npz"
                if sha256(path) != self.manifest["exports"][path.name]["sha256"]:
                    raise ValueError("Saved LDO features changed")
                with np.load(path, allow_pickle=False) as data:
                    points, descriptors = data["points"].copy(), None
            self.cache[stamp] = points, descriptors
        return self.cache[stamp]

    def assignments(self, query, historical):
        if self.method == "ldo":
            path = self.root / "learned_features" / f"pair_{query}_{historical}.npz"
            if sha256(path) != self.manifest["pairs"][path.name]["sha256"]:
                raise ValueError("Saved LDO assignments changed")
            with np.load(path, allow_pickle=False) as data:
                return data["indices"].copy()
        _, qd = self.features(query)
        _, hd = self.features(historical)
        if qd is None or hd is None or min(len(qd), len(hd)) < 2:
            return np.empty((0, 2), np.int64)

        def ratio(a, b):
            return {
                (m.queryIdx, m.trainIdx)
                for group in self.matcher.knnMatch(a, b, k=2)
                if len(group) == 2
                for m, n in [group]
                if m.distance < 0.75 * n.distance
            }

        forward, backward = ratio(qd, hd), ratio(hd, qd)
        return np.array(
            sorted(pair for pair in forward if pair[::-1] in backward), dtype=np.int64
        ).reshape(-1, 2)
