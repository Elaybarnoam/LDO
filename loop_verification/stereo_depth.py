"""Frame-local metric depth, independent of temporal matches and reference data."""

import csv
import hashlib
import json
from collections import Counter, OrderedDict
from pathlib import Path

import numpy as np
import yaml

from stereo_observations.dense import DenseStereo
from stereo_observations.geometry import reconstruct


def camera(path: Path):
    definition = yaml.safe_load(path.read_text())
    if (
        definition["camera_model"] != "pinhole"
        or definition["distortion_model"] != "radial-tangential"
    ):
        raise ValueError("Runtime stereo requires pinhole radial-tangential calibration")
    fx, fy, cx, cy = definition["intrinsics"]
    k = np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1]], dtype=float)
    distortion = np.array(definition["distortion_coefficients"], dtype=float)
    pose = np.asarray(definition["T_BS"]["data"], dtype=float).reshape(4, 4)
    if (
        not np.isfinite(pose).all()
        or not np.allclose(pose[3], [0, 0, 0, 1])
        or not np.allclose(pose[:3, :3].T @ pose[:3, :3], np.eye(3), atol=1e-5)
        or np.linalg.det(pose[:3, :3]) < 0
    ):
        raise ValueError("Invalid camera extrinsic calibration")
    return k, distortion, tuple(definition["resolution"]), pose


def load_stereo_policy(path: Path) -> dict:
    policy = yaml.safe_load(path.read_text())
    expected = {
        "stereo_model_python",
        "stereo_model_source",
        "stereo_model_checkpoint",
        "stereo_lr_max_error_px",
        "stereo_pixel_sigma_px",
        "stereo_minimum_depth_m",
        "stereo_maximum_depth_m",
        "stereo_minimum_parallax_degrees",
        "stereo_maximum_reprojection_px",
        "stereo_maximum_relative_depth_sigma",
    }
    if not isinstance(policy, dict) or set(policy) != expected:
        raise ValueError("Invalid observation-only stereo policy")
    for key in expected:
        value = policy[key]
        if key.startswith("stereo_model_"):
            if not isinstance(value, str) or not value:
                raise ValueError("Invalid stereo model artifact path")
        elif type(value) not in (int, float) or not np.isfinite(value) or value <= 0:
            raise ValueError(f"Invalid stereo parameter: {key}")
    if policy["stereo_minimum_depth_m"] >= policy["stereo_maximum_depth_m"]:
        raise ValueError("Invalid stereo depth interval")
    return policy


class StereoDepth:
    def __init__(self, sequence: Path, policy: dict, output: Path, cache_size: int = 64):
        self.sequence, self.policy, self.cache_size = sequence, dict(policy), cache_size
        self.cache = OrderedDict()
        self.k, self.distortion, self.size, t0 = camera(sequence / "mav0/cam0/sensor.yaml")
        k1, d1, size1, t1 = camera(sequence / "mav0/cam1/sensor.yaml")
        self.k1, self.d1 = k1, d1
        if size1 != self.size:
            raise ValueError("Stereo camera resolutions differ")
        self.relative = np.linalg.inv(t1) @ t0
        if np.linalg.norm(self.relative[:3, 3]) < 1e-6:
            raise ValueError("Zero stereo baseline")
        self.right = {}
        with (sequence / "mav0/cam1/data.csv").open() as stream:
            for row in csv.reader(stream):
                if row and not row[0].startswith("#"):
                    name, stamp = row[1].strip(), int(row[0])
                    if Path(name).name != name or stamp in self.right:
                        raise ValueError("Invalid right-camera index")
                    self.right[stamp] = sequence / "mav0/cam1/data" / name
        output.mkdir(parents=True, exist_ok=True)
        self.backend = DenseStereo(
            policy, self.k, self.distortion, k1, d1, self.size, self.relative, output
        )

    def frame(self, stamp: int, image: Path, points: np.ndarray):
        key = (stamp, hashlib.sha256(np.ascontiguousarray(points).tobytes()).hexdigest())
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        xyz = np.full((len(points), 3), np.nan)
        valid = np.zeros(len(points), dtype=bool)
        right = self.right.get(stamp)
        if right is None or not right.is_file():
            return xyz, valid, {"reason": "synchronized_right_image_missing"}
        if not len(points):
            return xyz, valid, {"reliable_depths": 0}
        right_pixels, associated, reasons, evidence = self.backend.match(
            stamp, image, right, points
        )
        indices = np.flatnonzero(associated)
        reconstructed, _, reliable, rejected = reconstruct(
            points[indices],
            right_pixels[indices],
            self.k,
            self.distortion,
            self.k1,
            self.d1,
            self.relative,
            self.policy,
        )
        xyz[indices] = reconstructed
        valid[indices] = reliable
        for i, reason in zip(indices, rejected, strict=True):
            reasons[i] = reason
        evidence.update(
            reliable_depths=int(valid.sum()),
            depth_failure_reasons=dict(Counter(r for r in reasons if r)),
        )
        result = xyz, valid, evidence
        self.cache[key] = result
        while len(self.cache) > self.cache_size:
            self.cache.popitem(last=False)
        return result

    def close(self):
        self.backend.close()
        self.cache.clear()

    def use_verified_cache(self, source: Path, source_policy: dict):
        """Reuse only frame-local predictions with matching observation settings.

        Caller validates model artifact provenance. Cached files are still checked
        against image/calibration/worker signatures and disparity content hashes.
        No reference pose or XYZ verdict is accepted by this interface.
        """
        if any(source_policy.get(k) != v for k, v in self.policy.items()):
            raise ValueError("Cached stereo observation policy differs")
        self.backend.cache_source = source
        self.backend.source_signature = self.backend._signature_for_policy(source_policy)
        # Recovery signatures also embed the legacy primary policy signature.
        self.backend.source_recovery_signature = hashlib.sha256(
            json.dumps(
                {
                    "primary_signature": self.backend.source_signature,
                    "rectification": self.backend.recovery_rectification.manifest(),
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()
