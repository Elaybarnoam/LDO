"""EuRoC reference sensor pose -> body -> actual cam0 optical frame."""

import csv
from pathlib import Path

import numpy as np
import yaml
from scipy.spatial.transform import Rotation


def sensor_transform(path):
    definition = yaml.safe_load(Path(path).read_text())
    data = definition["T_BS"]
    if data.get("rows") != 4 or data.get("cols") != 4:
        raise ValueError("Expected 4x4 sensor T_BS")
    transform = np.asarray(data["data"], dtype=float).reshape(4, 4)
    if not np.isfinite(transform).all() or not np.allclose(transform[3], [0, 0, 0, 1]):
        raise ValueError("Invalid sensor transform")
    if (
        not np.allclose(transform[:3, :3].T @ transform[:3, :3], np.eye(3), atol=1e-5)
        or np.linalg.det(transform[:3, :3]) < 0
    ):
        raise ValueError("Sensor rotation must be a proper rotation")
    return transform


class CameraPoses:
    def __init__(self, sequence, tolerance_ms):
        sequence = Path(sequence)
        folder = sequence / "mav0/state_groundtruth_estimate0"
        self.path = folder / "data.csv"
        self.tolerance_ns = round(tolerance_ms * 1_000_000)
        self.available = self.path.is_file() and (folder / "sensor.yaml").is_file()
        self.cache = {}
        if not self.available:
            return
        with self.path.open() as stream:
            rows = [row for row in csv.reader(stream) if row and not row[0].startswith("#")]
        self.stamps = np.array([int(row[0]) for row in rows], dtype=np.int64)
        self.states = np.array([[float(value) for value in row[1:8]] for row in rows], dtype=float)
        if (
            not len(rows)
            or not np.all(np.diff(self.stamps) > 0)
            or not np.isfinite(self.states).all()
        ):
            raise ValueError("Invalid ground-truth timestamp/pose data")
        norms = np.linalg.norm(self.states[:, 3:7], axis=1)
        if np.any(np.abs(norms - 1) > 0.01):
            raise ValueError("Invalid ground-truth quaternion")
        self.sensor_to_camera = np.linalg.inv(
            sensor_transform(folder / "sensor.yaml")
        ) @ sensor_transform(sequence / "mav0/cam0/sensor.yaml")

    def get(self, stamp):
        if not self.available:
            return None
        if stamp < self.stamps[0] or stamp > self.stamps[-1]:
            return None  # Never borrow a reference pose outside recorded coverage.
        if stamp in self.cache:
            return self.cache[stamp]
        index = int(np.searchsorted(self.stamps, stamp))
        choices = [i for i in (index - 1, index) if 0 <= i < len(self.stamps)]
        index = min(choices, key=lambda i: abs(int(self.stamps[i]) - stamp))
        delta = abs(int(self.stamps[index]) - stamp)
        if delta > self.tolerance_ns:
            self.cache[stamp] = None
            return None
        state = self.states[index]
        pose = np.eye(4)
        pose[:3, :3] = Rotation.from_quat(state[[4, 5, 6, 3]]).as_matrix()
        pose[:3, 3] = state[:3]
        result = (pose @ self.sensor_to_camera, int(self.stamps[index]), delta)
        self.cache[stamp] = result
        return result

    def eligibility(self, query_stamp, historical_stamp):
        """Mandatory admission rule shared by all detector evaluations."""
        missing = {}
        for role, stamp in (("query", query_stamp), ("historical", historical_stamp)):
            if self.get(stamp) is not None:
                continue
            if not self.available:
                reason = "ground_truth_unavailable"
            elif stamp < self.stamps[0]:
                reason = "before_ground_truth_start"
            elif stamp > self.stamps[-1]:
                reason = "after_ground_truth_end"
            else:
                reason = "pose_timestamp_out_of_tolerance"
            missing[role] = reason
        return {
            "eligible": not missing,
            "missing_reference_poses": missing,
            "pose_timestamp_tolerance_ms": self.tolerance_ns / 1_000_000,
        }

    def relative(self, query_stamp, historical_stamp):
        query, historical = self.get(query_stamp), self.get(historical_stamp)
        if query is None or historical is None:
            return None, {
                "available": False,
                "reason": "missing_ground_truth_or_timestamp_out_of_tolerance",
            }
        relative = np.linalg.inv(historical[0]) @ query[0]
        angle = Rotation.from_matrix(relative[:3, :3]).magnitude() * 180 / np.pi
        return relative, {
            "available": True,
            "camera_position_distance_m": float(np.linalg.norm(relative[:3, 3])),
            "camera_orientation_difference_degrees": float(angle),
            "query_pose_timestamp_ns": query[1],
            "historical_pose_timestamp_ns": historical[1],
            "query_pose_time_error_ns": query[2],
            "historical_pose_time_error_ns": historical[2],
        }
