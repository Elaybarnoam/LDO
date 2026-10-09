"""Offline pose error only; this module is never imported by the verifier."""

import numpy as np
from scipy.spatial.transform import Rotation

from .statistical_geometry import pose_consistency, rigid_transform


def assess_pose(
    estimate,
    reference,
    policy: dict,
    *,
    residual_covariance=None,
    calibrated=False,
    confidence=0.99,
) -> dict:
    if estimate is None or reference is None:
        return {"available": False, "reason": "pose_estimate_or_reference_missing"}
    estimate, reference = rigid_transform(estimate), rigid_transform(reference)
    angle = float(
        np.degrees(Rotation.from_matrix(reference[:3, :3].T @ estimate[:3, :3]).magnitude())
    )
    distance = float(np.linalg.norm(estimate[:3, 3] - reference[:3, 3]))
    result = {
        "available": True,
        "translation_error_m": distance,
        "rotation_error_degrees": angle,
        "within_tolerance": distance <= policy["maximum_translation_error_m"]
        and angle <= policy["maximum_rotation_error_degrees"],
    }

    if residual_covariance is not None:
        result["pose_statistics"] = pose_consistency(
            estimate, reference, residual_covariance, calibrated=calibrated, confidence=confidence
        )
    return result
