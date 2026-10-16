"""Raw-camera metric PnP/RANSAC; estimate T_HQ from query 3D to history 2D."""

from threading import Lock

import cv2
import numpy as np

_RNG_LOCK = Lock()


def estimate(points, pixels, k, distortion, seed, policy):
    with _RNG_LOCK:
        cv2.setRNGSeed(seed)
        success, rotation, translation, inliers = cv2.solvePnPRansac(
            np.ascontiguousarray(points, dtype=np.float64),
            np.ascontiguousarray(pixels, dtype=np.float64),
            k,
            distortion,
            iterationsCount=policy["ransac_iterations"],
            reprojectionError=policy["ransac_error_px"],
            confidence=policy["ransac_confidence"],
            flags=cv2.SOLVEPNP_EPNP,
        )
    if not success or inliers is None or len(inliers) < 6:
        return None
    indices = inliers.ravel()
    rotation, translation = cv2.solvePnPRefineLM(
        points[indices], pixels[indices], k, distortion, rotation, translation
    )
    if not np.isfinite(rotation).all() or not np.isfinite(translation).all():
        return None
    matrix = cv2.Rodrigues(rotation)[0]
    transformed = points @ matrix.T + translation.ravel()
    projected, jacobian = cv2.projectPoints(points, rotation, translation, k, distortion)
    errors = np.linalg.norm(projected[:, 0] - pixels, axis=1)
    mask = (errors <= policy["ransac_error_px"]) & (transformed[:, 2] > 0)
    if mask.sum() < 6:
        return None
    j = jacobian.reshape(len(points), 2, -1)[mask, :, :6].reshape(-1, 6)
    if not np.isfinite(j).all():
        return None
    j = j / np.maximum(np.linalg.norm(j, axis=0), 1e-15)
    singular = np.linalg.svd(j, compute_uv=False)
    condition = float(singular[0] / max(singular[-1], 1e-15))
    pose = np.eye(4)
    pose[:3, :3], pose[:3, 3] = matrix, translation.ravel()
    return (
        pose,
        mask,
        {
            "inliers": int(mask.sum()),
            "inlier_ratio": float(mask.mean()),
            "cheirality_ratio": float(np.mean(transformed[indices, 2] > 0)),
            "median_error_px": float(np.median(errors[mask])),
            "p95_error_px": float(np.percentile(errors[mask], 95)),
            "pose_condition": condition,
            "residuals_px": [float(e) if np.isfinite(e) else None for e in errors],
        },
    )
