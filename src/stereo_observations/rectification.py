"""Stereo rectification that retains both original cameras' field of view.

Expand a common canvas instead of zooming/cropping or shrinking the images.
The translation of both projection matrices preserves disparity scale and
horizontal epipolar geometry. Padding is explicitly masked, never evidence.
"""

from dataclasses import dataclass, replace

import cv2
import numpy as np
from numpy.typing import NDArray

RECTIFICATION_VERSION = 2


@dataclass(frozen=True, slots=True)
class Rectification:
    r0: NDArray
    r1: NDArray
    p0: NDArray
    p1: NDArray
    size: tuple[int, int]
    maps0: tuple[NDArray, NDArray]
    maps1: tuple[NDArray, NDArray]
    valid0: NDArray[np.bool_]
    valid1: NDArray[np.bool_]
    method: str = "expanded_canvas_original_disparity_scale"

    def manifest(self) -> dict:
        return {
            "version": RECTIFICATION_VERSION,
            "method": self.method,
            "size": list(self.size),
            "r0": self.r0.tolist(),
            "r1": self.r1.tolist(),
            "p0": self.p0.tolist(),
            "p1": self.p1.tolist(),
            "padding_is_evidence": False,
        }


def cropped_rectification(k0, d0, k1, d1, size, relative) -> Rectification:
    """Original projection retained for reproducible primary disparity."""
    r0, r1, p0, p1, *_ = cv2.stereoRectify(
        k0,
        d0,
        k1,
        d1,
        size,
        np.ascontiguousarray(relative[:3, :3]),
        np.ascontiguousarray(relative[:3, 3].reshape(3, 1)),
        flags=cv2.CALIB_ZERO_DISPARITY,
        alpha=0,
    )
    return replace(
        _make_layout(k0, d0, k1, d1, size, r0, r1, p0, p1, size), method="original_alpha0_crop"
    )


def full_field_rectification(k0, d0, k1, d1, size, relative) -> Rectification:
    """Retain raw sensor borders at the original alpha=0 projection scale."""
    width, height = size
    r0, r1, p0, p1, *_ = cv2.stereoRectify(
        k0,
        d0,
        k1,
        d1,
        size,
        np.ascontiguousarray(relative[:3, :3]),
        np.ascontiguousarray(relative[:3, 3].reshape(3, 1)),
        flags=cv2.CALIB_ZERO_DISPARITY,
        alpha=0,
    )
    # Include every border pixel, not just corners: distortion extrema may
    # occur between corners. Two extra pixels protect interpolation footprints.
    x, y = np.arange(width), np.arange(height)
    border = np.concatenate(
        [
            np.column_stack((x, np.zeros(width))),
            np.column_stack((x, np.full(width, height - 1))),
            np.column_stack((np.zeros(height), y)),
            np.column_stack((np.full(height, width - 1), y)),
        ]
    ).astype(np.float64)
    projected = np.concatenate(
        [
            cv2.undistortPoints(border[:, None], k, d, R=r, P=p)[:, 0]
            for k, d, r, p in ((k0, d0, r0, p0), (k1, d1, r1, p1))
        ]
    )
    if not np.isfinite(projected).all():
        raise ValueError("Nonfinite rectified sensor boundary")
    lower = np.floor(projected.min(axis=0)) - 2
    upper = np.ceil(projected.max(axis=0)) + 2
    canvas = tuple(map(int, upper - lower + 1))
    if canvas[0] * canvas[1] > 8 * width * height:
        raise ValueError("Rectification expands excessively; check calibration")
    shift = np.array([[1.0, 0.0, -lower[0]], [0.0, 1.0, -lower[1]], [0.0, 0.0, 1.0]])
    p0, p1 = shift @ p0, shift @ p1
    return _make_layout(k0, d0, k1, d1, size, r0, r1, p0, p1, canvas)


def _make_layout(k0, d0, k1, d1, size, r0, r1, p0, p1, canvas):
    width, height = size
    maps = [
        cv2.initUndistortRectifyMap(k, d, r, p, canvas, cv2.CV_32FC1)
        for k, d, r, p in ((k0, d0, r0, p0), (k1, d1, r1, p1))
    ]
    masks = [
        np.isfinite(mx)
        & np.isfinite(my)
        & (mx >= 0)
        & (mx < width - 1)
        & (my >= 0)
        & (my < height - 1)
        for mx, my in maps
    ]
    return Rectification(r0, r1, p0, p1, canvas, maps[0], maps[1], masks[0], masks[1])
