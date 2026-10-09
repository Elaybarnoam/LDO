"""Reference-only pinhole geometry; no detector output enters scene labels."""

import cv2
import numpy as np
from scipy.spatial.transform import Rotation

K = np.array([[320.0, 0.0, 319.5], [0.0, 320.0, 319.5], [0.0, 0.0, 1.0]])
CV_TO_NED = np.array([[0.0, 0.0, 1.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])


def camera_pose(row):
    row = np.asarray(row, dtype=float)
    if row.shape != (7,) or not np.isfinite(row).all() or abs(np.linalg.norm(row[3:]) - 1) > 1e-3:
        raise ValueError("Invalid TartanAir position/quaternion")
    pose = np.eye(4)
    pose[:3, :3] = Rotation.from_quat(row[3:]).as_matrix() @ CV_TO_NED
    pose[:3, 3] = row[:3]
    return pose


def decode_depth(path):
    image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if image is None or image.dtype != np.uint8 or image.shape != (640, 640, 4):
        raise ValueError(f"Invalid packed TartanAir depth: {path}")
    return np.ascontiguousarray(image).view("<f4").reshape(640, 640)


def sample_depth(depth, pixels, policy):
    pixels = np.asarray(pixels, dtype=float).reshape(-1, 2)
    valid = np.isfinite(pixels).all(axis=1)
    safe = np.where(np.isfinite(pixels), pixels, -1)
    xy = np.rint(safe).astype(int)
    valid &= (xy[:, 0] >= 1) & (xy[:, 0] < depth.shape[1] - 1)
    valid &= (xy[:, 1] >= 1) & (xy[:, 1] < depth.shape[0] - 1)
    x = np.clip(xy[:, 0], 1, depth.shape[1] - 2)
    y = np.clip(xy[:, 1], 1, depth.shape[0] - 2)
    neighbours = np.stack([depth[y + dy, x + dx] for dy in (-1, 0, 1) for dx in (-1, 0, 1)])
    z = depth[y, x].astype(float)
    valid &= np.isfinite(neighbours).all(axis=0)
    valid &= neighbours.min(axis=0) >= policy["minimum_depth_m"]
    valid &= neighbours.max(axis=0) <= policy["maximum_depth_m"]
    valid &= neighbours.max(axis=0) - neighbours.min(axis=0) <= policy[
        "depth_edge_relative_tolerance"
    ] * np.maximum(z, 1e-12)
    return z, valid


def backproject(pixels, z):
    xy1 = np.column_stack([pixels, np.ones(len(pixels))])
    return (xy1 @ np.linalg.inv(K).T) * np.asarray(z)[:, None]


def project(points):
    points = np.asarray(points)
    result = np.full((len(points), 2), np.nan)
    valid = np.isfinite(points).all(axis=1) & (points[:, 2] > 1e-9)
    homogeneous = points[valid] @ K.T
    result[valid] = homogeneous[:, :2] / homogeneous[:, 2:]
    return result, valid


def visibility(points, target_depth, transform, policy):
    mapped = points @ transform[:3, :3].T + transform[:3, 3]
    pixels, forward = project(mapped)
    z, valid = sample_depth(target_depth, pixels, policy)
    tolerance = np.maximum(
        policy["depth_absolute_tolerance_m"], policy["depth_relative_tolerance"] * np.maximum(z, 0)
    )
    visible = forward & valid & (np.abs(mapped[:, 2] - z) <= tolerance)
    return pixels, visible


def overlap(query_depth, historical_depth, relative, policy):
    # A fixed image grid is independent of either detector's feature locations.
    coordinates = np.arange(policy["grid_step"] / 2, 640, policy["grid_step"])
    x, y = np.meshgrid(coordinates, coordinates)
    pixels = np.column_stack([x.ravel(), y.ravel()])
    fractions, upper_bounds, valid_fractions = [], [], []
    for source, target, transform in (
        (query_depth, historical_depth, relative),
        (historical_depth, query_depth, np.linalg.inv(relative)),
    ):
        z, valid = sample_depth(source, pixels, policy)
        points = backproject(pixels, z)
        projected, visible = visibility(points, target, transform, policy)
        mapped = points @ transform[:3, :3].T + transform[:3, 3]
        _, forward = project(mapped)
        _, target_valid = sample_depth(target, projected, policy)
        # Points behind/outside the target are known not to overlap. Depth-edge,
        # missing-depth and near-border observations remain uncertain.
        inside = forward & (projected[:, 0] >= 0) & (projected[:, 0] <= 639)
        inside &= (projected[:, 1] >= 0) & (projected[:, 1] <= 639)
        uncertain = ~valid | (valid & inside & ~target_valid)
        lower = float(np.mean(valid & visible))
        fractions.append(lower)
        upper_bounds.append(lower + float(np.mean(uncertain)))
        valid_fractions.append(float(np.mean(valid)))
    lower, upper = min(fractions), min(upper_bounds)
    threshold = policy["loop_overlap"]
    label = "loop" if lower >= threshold else "non_loop" if upper < threshold else "unknown"
    return {
        "label": label,
        "symmetric_overlap": lower,
        "symmetric_overlap_bounds": [lower, upper],
        "directional_overlap": fractions,
        "directional_overlap_upper_bounds": upper_bounds,
        "valid_reference_fraction": valid_fractions,
    }


def check_features(
    query_pixels, historical_pixels, query_depth, historical_depth, relative, policy
):
    q = np.asarray(query_pixels, dtype=float).reshape(-1, 2)
    h = np.asarray(historical_pixels, dtype=float).reshape(-1, 2)
    if q.shape != h.shape:
        raise ValueError("Feature-pair shapes differ")
    qz, qvalid = sample_depth(query_depth, q, policy)
    hz, hvalid = sample_depth(historical_depth, h, policy)
    qxyz, hxyz = backproject(q, qz), backproject(h, hz)
    mapped = qxyz @ relative[:3, :3].T + relative[:3, 3]
    predicted_h, valid_h = project(mapped)
    reverse = np.linalg.inv(relative)
    predicted_q, valid_q = project(hxyz @ reverse[:3, :3].T + reverse[:3, 3])
    judged = qvalid & hvalid
    xyz_error = np.linalg.norm(mapped - hxyz, axis=1)
    pixel_error = np.maximum(
        np.linalg.norm(predicted_h - h, axis=1), np.linalg.norm(predicted_q - q, axis=1)
    )
    distance_gate = np.maximum(
        policy["feature_xyz_tolerance_m"],
        policy["feature_xyz_relative_tolerance"] * np.maximum(qz, hz),
    )
    supported = (
        judged
        & valid_h
        & valid_q
        & (xyz_error <= distance_gate)
        & (pixel_error <= policy["feature_pixel_tolerance"])
    )
    verdicts = np.full(len(q), "untestable", dtype="U12")
    verdicts[judged] = "contradicted"
    verdicts[supported] = "supported"
    return {
        "counts": {
            key: int(np.sum(verdicts == key)) for key in ("supported", "contradicted", "untestable")
        },
        "verdicts": verdicts,
        "xyz_error_m": xyz_error,
        "pixel_error": pixel_error,
        "query_reference_depth_valid": qvalid,
        "historical_reference_depth_valid": hvalid,
    }
