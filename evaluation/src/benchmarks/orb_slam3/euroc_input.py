"""Validate source streams and preserve their integer timestamp associations."""

import csv
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EurocInput:
    sequence_path: Path
    timestamps_path: Path
    frame_count: int
    imu_count: int
    unpaired_camera_frames: int


def _rows(path: Path, width: int) -> list[list[str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = [row for row in csv.reader(stream) if row and not row[0].startswith("#")]
    if not rows or any(len(row) != width for row in rows):
        raise ValueError(f"Empty or malformed stream: {path}")
    timestamps = [int(row[0]) for row in rows]
    if any(value <= 0 for value in timestamps) or any(a >= b for a, b in zip(timestamps, timestamps[1:])):
        raise ValueError(f"Timestamps must be positive and strictly increasing: {path}")
    return rows


def prepare(sequence_path: Path, workspace: Path) -> EurocInput:
    """Return matched stereo input; leave downloaded EuRoC files unchanged."""
    cameras = []
    for name in ("cam0", "cam1"):
        folder = sequence_path / "mav0" / name
        if not (folder / "sensor.yaml").is_file():
            raise ValueError(f"Missing calibration: {folder}")
        rows = _rows(folder / "data.csv", 2)
        with os.scandir(folder / "data") as entries:
            available_images = {entry.name for entry in entries if entry.is_file()}
        timestamps = set()
        for timestamp, filename in rows:
            # The upstream EuRoC reader constructs <integer timestamp>.png paths.
            if filename != f"{timestamp}.png" or filename not in available_images:
                raise ValueError(f"Missing or unsupported EuRoC image: {folder / 'data' / filename}")
            timestamps.add(int(timestamp))
        cameras.append(timestamps)
    shared = sorted(cameras[0] & cameras[1])
    if len(shared) < 2:
        raise ValueError("At least two matched stereo frames are required")
    imu_folder = sequence_path / "mav0/imu0"
    if not (imu_folder / "sensor.yaml").is_file():
        raise ValueError("Missing IMU calibration")
    imu = _rows(imu_folder / "data.csv", 7)
    import math
    if any(not math.isfinite(float(value)) for row in imu for value in row[1:]):
        raise ValueError("IMU measurements must be finite")
    if int(imu[0][0]) > shared[0] or int(imu[-1][0]) < shared[-1]:
        raise ValueError("IMU stream does not cover matched camera frames")
    timestamps_path = workspace / "stereo_timestamps.txt"
    timestamps_path.write_text("".join(f"{timestamp}\n" for timestamp in shared), encoding="ascii")
    return EurocInput(sequence_path, timestamps_path, len(shared), len(imu),
                      len(cameras[0] ^ cameras[1]))
