"""Reference surface sampling with no metric distance cutoff or fitted geometry."""

import numpy as np

from tasks.reference_geometry.geometry import backproject, project


def sample_surface(depth, semantics, pixels, known_labels, sky_label, policy):
    """Interpolate inverse Z only within a valid, continuous non-sky footprint.

    Integer array coordinates denote pixel centers. Zero-weight neighbours cannot
    invalidate a sample; no nearest-side selection is made at mixed-depth cells.
    """
    if depth.ndim != 2 or semantics.shape != depth.shape:
        raise ValueError("Reference depth and semantic shapes differ")
    points = np.asarray(pixels, float).reshape(-1, 2)
    height, width = depth.shape
    inside = np.isfinite(points).all(axis=1)
    inside &= (points[:, 0] >= 0) & (points[:, 0] <= width - 1)
    inside &= (points[:, 1] >= 0) & (points[:, 1] <= height - 1)
    safe = np.clip(np.where(np.isfinite(points), points, 0), [0, 0], [width - 1, height - 1])
    base = np.floor(safe).astype(int)
    dx, dy = (safe - base).T
    weights = np.array([(1 - dx) * (1 - dy), dx * (1 - dy), (1 - dx) * dy, dx * dy])
    active = weights > 0
    values, classes = [], []
    for ox, oy in ((0, 0), (1, 0), (0, 1), (1, 1)):
        x, y = np.minimum(base[:, 0] + ox, width - 1), np.minimum(base[:, 1] + oy, height - 1)
        values.append(depth[y, x].astype(float))
        classes.append(semantics[y, x])
    values, classes = np.array(values), np.array(classes)
    positive = np.isfinite(values) & (values > 0)
    lo = np.min(np.where(active, values, np.inf), axis=0)
    hi = np.max(np.where(active, values, -np.inf), axis=0)
    inverse = np.where(active, weights / np.where(positive, values, 1), 0).sum(axis=0)
    z = 1 / np.maximum(inverse, np.finfo(float).tiny)
    reason = np.full(len(points), "usable", dtype="U40")
    reason[(hi - lo) > policy["depth_edge_relative_tolerance"] * z] = "ambiguous_depth_boundary"
    reason[np.any(active & ~np.isin(classes, list(known_labels)), axis=0)] = "unmapped_semantics"
    reason[np.any(active & (classes == sky_label), axis=0)] = "sky"
    reason[np.any(active & ~positive, axis=0)] = "nonpositive_or_nonfinite_depth"
    reason[~inside] = "outside_image_or_nonfinite_pixel"
    valid = reason == "usable"
    z[~valid] = np.nan
    return z, valid, reason


def check_features(
    q,
    h,
    query_depth,
    historical_depth,
    query_sem,
    historical_sem,
    relative,
    known_labels,
    sky_label,
    policy,
):
    q, h = np.asarray(q, float).reshape(-1, 2), np.asarray(h, float).reshape(-1, 2)
    if q.shape != h.shape:
        raise ValueError("Feature-pair shapes differ")
    qz, qvalid, qr = sample_surface(query_depth, query_sem, q, known_labels, sky_label, policy)
    hz, hvalid, hr = sample_surface(
        historical_depth, historical_sem, h, known_labels, sky_label, policy
    )
    qxyz, hxyz = backproject(q, qz), backproject(h, hz)
    mapped = qxyz @ relative[:3, :3].T + relative[:3, 3]
    predicted_h, hf = project(mapped)
    reverse = np.linalg.inv(relative)
    predicted_q, qf = project(hxyz @ reverse[:3, :3].T + reverse[:3, 3])
    xyz_error = np.linalg.norm(mapped - hxyz, axis=1)
    pixel_error = np.maximum(
        np.linalg.norm(predicted_h - h, axis=1), np.linalg.norm(predicted_q - q, axis=1)
    )
    gate = np.maximum(
        policy["feature_xyz_tolerance_m"],
        policy["feature_xyz_relative_tolerance"] * np.maximum(qz, hz),
    )
    judged = qvalid & hvalid
    supported = (
        judged & hf & qf & (xyz_error <= gate) & (pixel_error <= policy["feature_pixel_tolerance"])
    )
    verdicts = np.full(len(q), "untestable", dtype="U12")
    verdicts[judged] = "contradicted"
    verdicts[supported] = "supported"
    return {
        "verdicts": verdicts,
        "query_reason": qr,
        "historical_reason": hr,
        "query_depth_m": qz,
        "historical_depth_m": hz,
        "xyz_error_m": xyz_error,
        "pixel_error": pixel_error,
    }
