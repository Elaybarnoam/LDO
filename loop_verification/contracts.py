"""Runtime inputs contain observations, never reference poses or labels."""

from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True, slots=True)
class VerificationInput:
    query_timestamp_ns: int
    historical_timestamp_ns: int
    assignment_ids: NDArray
    query_camera_xyz: NDArray
    historical_pixels: NDArray
    depth_valid: NDArray
    camera_matrix: NDArray
    distortion: NDArray
    image_size: tuple[int, int]

    def __post_init__(self):
        if (
            type(self.query_timestamp_ns) is not int
            or type(self.historical_timestamp_ns) is not int
            or self.historical_timestamp_ns >= self.query_timestamp_ns
        ):
            raise ValueError("Verification requires integer chronological pair timestamps")
        n = len(self.assignment_ids)
        if (
            self.assignment_ids.shape != (n, 2)
            or self.assignment_ids.dtype != np.int64
            or self.query_camera_xyz.shape != (n, 3)
            or self.historical_pixels.shape != (n, 2)
            or self.depth_valid.shape != (n,)
            or self.depth_valid.dtype != np.bool_
        ):
            raise ValueError("Invalid assignment or observation shapes")
        if np.any(self.assignment_ids < 0) or any(
            len(np.unique(self.assignment_ids[:, i])) != n for i in (0, 1)
        ):
            raise ValueError("Assignments must have unique nonnegative feature IDs")
        if (
            self.camera_matrix.shape != (3, 3)
            or not np.isfinite(self.camera_matrix).all()
            or self.camera_matrix[0, 0] <= 0
            or self.camera_matrix[1, 1] <= 0
            or not np.allclose(self.camera_matrix[2], [0, 0, 1])
            or not np.isfinite(self.distortion).all()
        ):
            raise ValueError("Invalid camera calibration")
        size = np.asarray(self.image_size)
        if (
            np.any(size <= 0)
            or not np.isfinite(self.historical_pixels).all()
            or np.any(self.historical_pixels < 0)
            or np.any(self.historical_pixels >= size)
        ):
            raise ValueError("Historical pixels must be inside the raw camera image")
        if np.any(~np.isfinite(self.query_camera_xyz[self.depth_valid])) or np.any(
            self.query_camera_xyz[self.depth_valid, 2] <= 0
        ):
            raise ValueError("Valid stereo observations require finite positive depths")
        for value in (
            self.assignment_ids,
            self.query_camera_xyz,
            self.historical_pixels,
            self.depth_valid,
            self.camera_matrix,
            self.distortion,
        ):
            value.flags.writeable = False


@dataclass(frozen=True, slots=True)
class VerificationResult:
    status: Literal["accepted", "rejected", "insufficient_evidence"]
    reason: str
    transform_historical_from_query: NDArray | None
    inlier_assignment_ids: tuple[tuple[int, int], ...]
    diagnostics: dict

    def to_dict(self):
        return {
            "status": self.status,
            "reason": self.reason,
            "T_HQ": self.transform_historical_from_query.tolist()
            if self.transform_historical_from_query is not None
            else None,
            "inlier_assignment_ids": [list(pair) for pair in self.inlier_assignment_ids],
            "diagnostics": self.diagnostics,
        }
