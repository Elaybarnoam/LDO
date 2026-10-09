"""Calibrated disparity with independently verified field-of-view recovery."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import cv2
import numpy as np

from .rectification import cropped_rectification, full_field_rectification


def sample(array, points):
    points = np.asarray(points, np.float32).reshape(-1, 2)
    return cv2.remap(
        array,
        points[:, 0].reshape(-1, 1),
        points[:, 1].reshape(-1, 1),
        cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=float("nan"),
    ).reshape(-1)


def correspondences(
    points,
    left_disparity,
    right_disparity,
    k0,
    d0,
    r0,
    p0,
    right_maps,
    tolerance,
    left_valid=None,
    right_valid=None,
    raw_size=None,
):
    if not len(points):
        return np.empty((0, 2)), np.zeros(0, bool), []
    rectified = cv2.undistortPoints(
        np.asarray(points, float).reshape(-1, 1, 2), k0, d0, R=r0, P=p0
    ).reshape(-1, 2)
    disparity = sample(left_disparity, rectified)
    right = rectified.copy()
    right[:, 0] -= disparity
    reverse = sample(right_disparity, right)
    raw_right = np.column_stack([sample(m, right) for m in right_maps])
    height, width = left_disparity.shape
    raw_width, raw_height = raw_size or (width, height)
    left_inside = (
        (rectified[:, 0] >= 0)
        & (rectified[:, 0] < width - 1)
        & (rectified[:, 1] >= 0)
        & (rectified[:, 1] < height - 1)
    )
    left_content = (
        sample(left_valid.astype(np.float32), rectified) >= 1 - 1e-6
        if left_valid is not None
        else left_inside
    )
    right_content = (
        sample(right_valid.astype(np.float32), right) >= 1 - 1e-6
        if right_valid is not None
        else np.ones(len(points), bool)
    )
    reliable, reasons = np.ones(len(points), bool), []
    for i in range(len(points)):
        reason = None
        if not left_inside[i]:
            reason = "rectified_observation_outside_canvas"
        elif not left_content[i]:
            reason = "rectified_observation_outside_sensor_content"
        elif not np.isfinite(disparity[i]) or disparity[i] <= 0:
            reason = "dense_disparity_invalid"
        elif not np.isfinite(raw_right[i]).all() or not (
            0 <= right[i, 0] < width - 1 and 0 <= right[i, 1] < height - 1
        ):
            reason = "stereo_occluded_or_outside_image"
        elif not right_content[i]:
            reason = "stereo_correspondence_outside_sensor_content"
        elif (
            not np.isfinite(reverse[i])
            or reverse[i] <= 0
            or abs(disparity[i] - reverse[i]) > tolerance
        ):
            reason = "stereo_left_right_inconsistent"
        elif not (0 <= raw_right[i, 0] < raw_width - 1 and 0 <= raw_right[i, 1] < raw_height - 1):
            reason = "raw_correspondence_outside_image"
        reliable[i] = reason is None
        reasons.append(reason)
    return raw_right, reliable, reasons


class DenseStereo:
    def __init__(self, policy, k0, d0, k1, d1, size, relative, output, worker_path=None):
        self.policy = policy
        manifest = json.loads(
            (Path(policy["stereo_model_source"]) / "ldo-install.json").read_text()
        )
        for filename, expected in manifest["artifacts"].items():
            artifact = Path(filename)
            if not artifact.exists() and artifact.name == "stereo-runtime.lock":
                artifact = Path(__file__).with_name("stereo-runtime.lock")
            if hashlib.sha256(artifact.read_bytes()).hexdigest() != expected:
                raise ValueError(f"Pinned stereo artifact changed: {filename}")
        self.output = Path(output)
        self.output.mkdir(exist_ok=True)
        self.rectification = cropped_rectification(k0, d0, k1, d1, size, relative)
        self.recovery_rectification = full_field_rectification(k0, d0, k1, d1, size, relative)
        layout = self.rectification
        self.r0, self.r1, self.p0, self.p1 = layout.r0, layout.r1, layout.p0, layout.p1
        self.maps = [layout.maps0, layout.maps1]
        self.raw_size, self.k0, self.d0 = size, k0, d0
        self.process, self.log = None, None
        calibration = [k0.tolist(), d0.tolist(), k1.tolist(), d1.tolist(), relative.tolist()]
        worker = Path(worker_path) if worker_path else Path(__file__).with_name("stereo_worker.py")
        self.worker = worker
        worker_sha = hashlib.sha256(worker.read_bytes()).hexdigest()

        def signature(saved_policy):
            # Original primary rectification/inference is unchanged. Sampling
            # changes are recorded separately and cannot change cached disparity.
            return hashlib.sha256(
                json.dumps(
                    {
                        "policy": saved_policy,
                        "calibration": calibration,
                        "worker_sha256": worker_sha,
                    },
                    sort_keys=True,
                ).encode()
            ).hexdigest()

        self.signature = signature(policy)
        self.recovery_signature = hashlib.sha256(
            json.dumps(
                {
                    "primary_signature": self.signature,
                    "rectification": self.recovery_rectification.manifest(),
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()
        self.cache_source = None
        self._signature_for_policy = signature

    def preparation_manifest(self):
        return {
            "version": 2,
            "method": "original_primary_with_full_field_recovery",
            "primary_size": list(self.rectification.size),
            "recovery": self.recovery_rectification.manifest(),
            "recovery_eligibility": "primary observation outside rectified canvas or sensor content",
            "selection_uses_reference_poses": False,
            "selection_uses_temporal_correspondence": False,
        }

    def start(self):
        if self.process is not None:
            return
        self.log = (self.output / "inference.stderr.log").open("w")
        command = [
            self.policy["stereo_model_python"],
            str(self.worker),
            "--checkpoint",
            self.policy["stereo_model_checkpoint"],
        ]
        self.process = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log, text=True
        )
        ready = self.process.stdout.readline()
        if not ready or not json.loads(ready).get("ready"):
            self.close()
            raise RuntimeError(
                f"Stereo model failed to initialize; see {self.output / 'inference.stderr.log'}"
            )
        self.runtime = json.loads(ready)

    def _disparity(
        self, stamp, left_path, right_path, layout, directory, signature, recovery=False
    ):
        directory.mkdir(exist_ok=True)
        output, cache_manifest = directory / f"{stamp}.npz", directory / f"{stamp}.json"
        inputs = {
            "signature": signature,
            "left_sha256": hashlib.sha256(Path(left_path).read_bytes()).hexdigest(),
            "right_sha256": hashlib.sha256(Path(right_path).read_bytes()).hexdigest(),
        }
        if not output.exists() and self.cache_source is not None:
            source_dir = self.cache_source / "full_field" if recovery else self.cache_source
            source = source_dir / output.name
            source_manifest = source.with_suffix(".json")
            if source.is_file() and source_manifest.is_file():
                saved = json.loads(source_manifest.read_text())
                expected = {
                    **inputs,
                    "signature": getattr(self, "source_recovery_signature", signature)
                    if recovery
                    else self.source_signature,
                }
                if (
                    saved["inputs"] != expected
                    or hashlib.sha256(source.read_bytes()).hexdigest() != saved["disparity_sha256"]
                ):
                    raise ValueError(f"Stereo source cache failed integrity validation: {source}")
                shutil.copyfile(source, output)
                cache_manifest.write_text(
                    json.dumps({**saved, "inputs": inputs, "reused_from": str(source)}, indent=2)
                )
        cached = json.loads(cache_manifest.read_text()) if cache_manifest.is_file() else None
        if (
            output.is_file()
            and cached
            and cached["inputs"] == inputs
            and hashlib.sha256(output.read_bytes()).hexdigest() == cached["disparity_sha256"]
        ):
            self.runtime = cached["runtime"]
        else:
            self.start()
            images = [cv2.imread(str(p), cv2.IMREAD_GRAYSCALE) for p in (left_path, right_path)]
            if any(image is None for image in images):
                raise ValueError("Missing stereo input image")
            names = [directory / f"{stamp}_{camera}.png" for camera in ("cam0", "cam1")]
            for image, maps, name in zip(images, (layout.maps0, layout.maps1), names, strict=True):
                rectified = cv2.remap(image, *maps, cv2.INTER_LINEAR)
                if not cv2.imwrite(str(name), rectified):
                    raise RuntimeError("Cannot save rectified stereo input")
            request = {"left": str(names[0]), "right": str(names[1]), "output": str(output)}
            self.process.stdin.write(json.dumps(request) + "\n")
            self.process.stdin.flush()
            reply = self.process.stdout.readline()
            if not reply or json.loads(reply).get("output") != str(output):
                raise RuntimeError(
                    f"Stereo inference failed; see {self.output / 'inference.stderr.log'}"
                )
            cached = {
                "inputs": inputs,
                "runtime": self.runtime,
                "rectification": layout.manifest(),
                "disparity_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            }
            cache_manifest.write_text(json.dumps(cached, indent=2))
        with np.load(output) as data:
            left, right = data["left"], data["right"]
        if left.shape != layout.size[::-1] or right.shape != layout.size[::-1]:
            raise ValueError("Cached disparity dimensions differ from rectification canvas")
        return (
            left,
            right,
            {
                "disparity_file": str(output),
                "disparity_sha256": cached["disparity_sha256"],
                "reused_from": cached.get("reused_from"),
            },
        )

    def _sample_layout(self, points, layout, disparities):
        return correspondences(
            points,
            *disparities,
            self.k0,
            self.d0,
            layout.r0,
            layout.p0,
            layout.maps1,
            self.policy["stereo_lr_max_error_px"],
            layout.valid0,
            layout.valid1,
            self.raw_size,
        )

    def match(self, stamp, left_path, right_path, points):
        layout = self.rectification
        dl, dr, primary = self._disparity(
            stamp, left_path, right_path, layout, self.output, self.signature
        )
        right, valid, reasons = self._sample_layout(points, layout, (dl, dr))
        eligible = np.array(
            [
                r
                in {
                    "rectified_observation_outside_canvas",
                    "rectified_observation_outside_sensor_content",
                }
                for r in reasons
            ]
        )
        recovery, recovered = None, []
        if eligible.any() and hasattr(self, "recovery_rectification"):
            expanded = self.recovery_rectification
            el, er, recovery = self._disparity(
                stamp,
                left_path,
                right_path,
                expanded,
                self.output / "full_field",
                self.recovery_signature,
                recovery=True,
            )
            indices = np.flatnonzero(eligible)
            rp, ok, rejected = self._sample_layout(np.asarray(points)[indices], expanded, (el, er))
            for j, i in enumerate(indices):
                reasons[i] = rejected[j]
                if ok[j]:
                    right[i], valid[i] = rp[j], True
                    recovered.append(int(i))
        return (
            right,
            valid,
            reasons,
            {
                "backend": "fast_foundationstereo",
                "runtime": self.runtime,
                **primary,
                "preparation": self.preparation_manifest()
                if hasattr(self, "recovery_rectification")
                else None,
                "full_field": recovery,
                "recovery_attempted": int(eligible.sum()),
                "primary_outside_feature_ids": np.flatnonzero(eligible).tolist(),
                "recovered_feature_ids": recovered,
            },
        )

    def close(self):
        if self.process is not None:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
            for stream in (self.process.stdin, self.process.stdout):
                stream.close()
            self.process = None
        if self.log is not None:
            self.log.close()
            self.log = None
