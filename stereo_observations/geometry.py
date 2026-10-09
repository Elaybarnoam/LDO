"""Frozen raw-camera stereo reconstruction; no absolute/reference poses."""

import cv2
import numpy as np


def project(points, k, distortion):
    return cv2.projectPoints(
        np.asarray(points, dtype=np.float64).reshape(-1, 3), np.zeros(3), np.zeros(3), k, distortion
    )[0].reshape(-1, 2)


def triangulate(left_pixels, right_pixels, k0, d0, k1, d1, right_from_left):
    left = cv2.undistortPoints(
        np.asarray(left_pixels, dtype=float).reshape(-1, 1, 2), k0, d0
    ).reshape(-1, 2)
    right = cv2.undistortPoints(
        np.asarray(right_pixels, dtype=float).reshape(-1, 1, 2), k1, d1
    ).reshape(-1, 2)
    p0 = np.column_stack((np.eye(3), np.zeros(3)))
    p1 = right_from_left[:3]
    homogeneous = cv2.triangulatePoints(p0, p1, left.T, right.T).T
    with np.errstate(divide="ignore", invalid="ignore"):
        return homogeneous[:, :3] / homogeneous[:, 3:]


def reconstruct(left_pixels, right_pixels, k0, d0, k1, d1, right_from_left, policy):
    """Return XYZ in original cam0 axes, covariance, reliability and reason."""
    left_pixels, right_pixels = np.asarray(left_pixels, float), np.asarray(right_pixels, float)
    if not len(left_pixels):
        return np.empty((0, 3)), np.empty((0, 3, 3)), np.zeros(0, bool), []
    xyz = triangulate(left_pixels, right_pixels, k0, d0, k1, d1, right_from_left)
    covariance = np.full((len(xyz), 3, 3), np.nan)
    finite = np.isfinite(xyz).all(axis=1)
    # Numerical Jacobian in raw distorted pixel coordinates, four measurements.
    if finite.any():
        a, b = left_pixels[finite], right_pixels[finite]
        jacobian = np.zeros((len(a), 3, 4))
        step = 0.25
        for axis in range(4):
            plus_a, minus_a, plus_b, minus_b = a.copy(), a.copy(), b.copy(), b.copy()
            if axis < 2:
                plus_a[:, axis] += step
                minus_a[:, axis] -= step
            else:
                plus_b[:, axis - 2] += step
                minus_b[:, axis - 2] -= step
            plus = triangulate(plus_a, plus_b, k0, d0, k1, d1, right_from_left)
            minus = triangulate(minus_a, minus_b, k0, d0, k1, d1, right_from_left)
            jacobian[:, :, axis] = (plus - minus) / (2 * step)
        covariance[finite] = (
            jacobian @ np.swapaxes(jacobian, 1, 2) * policy["stereo_pixel_sigma_px"] ** 2
        )
    right_xyz = xyz @ right_from_left[:3, :3].T + right_from_left[:3, 3]
    error = np.full(len(xyz), np.inf)
    if finite.any():
        error[finite] = np.maximum(
            np.linalg.norm(project(xyz[finite], k0, d0) - left_pixels[finite], axis=1),
            np.linalg.norm(project(right_xyz[finite], k1, d1) - right_pixels[finite], axis=1),
        )
    right_center = -right_from_left[:3, :3].T @ right_from_left[:3, 3]
    with np.errstate(divide="ignore", invalid="ignore"):
        ray0 = xyz / np.linalg.norm(xyz, axis=1)[:, None]
        ray1 = (xyz - right_center) / np.linalg.norm(xyz - right_center, axis=1)[:, None]
        parallax = np.degrees(np.arccos(np.clip(np.sum(ray0 * ray1, axis=1), -1, 1)))
        relative_sigma = np.sqrt(covariance[:, 2, 2]) / xyz[:, 2]
    reliable, reasons = np.ones(len(xyz), bool), []
    for index in range(len(xyz)):
        reason = None
        if not finite[index] or not np.isfinite(covariance[index]).all():
            reason = "nonfinite_triangulation"
        elif xyz[index, 2] <= 0 or right_xyz[index, 2] <= 0:
            reason = "nonpositive_depth"
        elif (
            not policy["stereo_minimum_depth_m"]
            <= xyz[index, 2]
            <= policy["stereo_maximum_depth_m"]
        ):
            reason = "depth_out_of_range"
        elif error[index] > policy["stereo_maximum_reprojection_px"]:
            reason = "stereo_reprojection_error"
        elif parallax[index] < policy["stereo_minimum_parallax_degrees"]:
            reason = "low_stereo_parallax"
        elif relative_sigma[index] > policy["stereo_maximum_relative_depth_sigma"]:
            reason = "uncertain_stereo_depth"
        reliable[index] = reason is None
        reasons.append(reason)
    return xyz, covariance, reliable, reasons
