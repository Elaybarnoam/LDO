"""Optional calibrated geometry checks; never imported by runtime verification.

Covariance belongs to the stated residual coordinates, not raw pose parameters.
No assumed noise is silently treated as calibrated uncertainty.
"""

import numpy as np
from scipy.spatial.transform import Rotation
from scipy.stats import chi2


def rigid_transform(value):
    """Validate a homogeneous rigid transform without repairing its rotation."""
    value = np.asarray(value, dtype=float)
    if value.shape != (4, 4) or not np.isfinite(value).all():
        raise ValueError("Transform must be a finite 4x4 matrix")
    r = value[:3, :3]
    if (
        not np.allclose(value[3], [0, 0, 0, 1], atol=1e-8, rtol=0)
        or not np.allclose(r.T @ r, np.eye(3), atol=1e-6, rtol=0)
        or not np.isclose(np.linalg.det(r), 1, atol=1e-6, rtol=0)
    ):
        raise ValueError("Transform must be rigid with a proper rotation")
    return value


def _covariance(value, size, positive=True):
    value = np.asarray(value, dtype=float)
    if (
        value.shape != (size, size)
        or not np.isfinite(value).all()
        or not np.allclose(value, value.T, atol=1e-12, rtol=1e-8)
    ):
        raise ValueError("Covariance must be finite, symmetric and correctly sized")
    eigenvalues = np.linalg.eigvalsh(value)
    if (positive and eigenvalues[0] <= 0) or eigenvalues[0] < -1e-12:
        raise ValueError(
            "Covariance must be positive definite (joint covariance may be semidefinite)"
        )
    return value


def gaussian_consistency(residual, covariance=None, *, calibrated=False, confidence=0.99):
    """Conditional Gaussian compatibility, not proof of correspondence identity."""
    if type(calibrated) is not bool:
        raise ValueError("Calibration declaration must be boolean")
    residual = np.asarray(residual, dtype=float)
    if residual.ndim != 1 or not residual.size or not np.isfinite(residual).all():
        raise ValueError("Residual must be a nonempty finite vector")
    if not 0 < confidence < 1:
        raise ValueError("Confidence must be between zero and one")
    if covariance is None:
        return {"available": False, "reason": "residual_covariance_missing"}
    covariance = _covariance(covariance, residual.size)
    distance = float(residual @ np.linalg.solve(covariance, residual))
    result = {
        "available": bool(calibrated),
        "mahalanobis_squared": distance,
        "degrees_of_freedom": int(residual.size),
        "confidence": confidence,
        "threshold": float(chi2.ppf(confidence, residual.size)),
        "assumption": "calibrated_covariance_and_approximately_gaussian_residual",
    }
    if calibrated:
        result.update(
            compatible=distance <= result["threshold"],
            tail_probability=float(chi2.sf(distance, residual.size)),
        )
    else:
        result["reason"] = "covariance_not_calibrated_no_statistical_verdict"
    return result


def world_point_consistency(
    query_world, historical_world, joint_covariance=None, *, calibrated=False, confidence=0.99
):
    """Joint covariance order: query world XYZ, historical world XYZ.

    Caller propagates stereo, poses and calibration including cross-correlation.
    """
    points = np.asarray([query_world, historical_world], dtype=float)
    if points.shape != (2, 3) or not np.isfinite(points).all():
        raise ValueError("World points must be two finite XYZ vectors")
    residual = points[0] - points[1]
    covariance = None
    if joint_covariance is not None:
        joint = _covariance(joint_covariance, 6, positive=False)
        jacobian = np.concatenate([np.eye(3), -np.eye(3)], axis=1)
        covariance = jacobian @ joint @ jacobian.T
    return {
        "residual_world_m": residual.tolist(),
        "distance_m": float(np.linalg.norm(residual)),
        "statistical_consistency": gaussian_consistency(
            residual, covariance, calibrated=calibrated, confidence=confidence
        ),
    }


def pose_residual(estimate, reference):
    """Log(reference^-1 estimate), [rho metres, phi radians], reference tangent."""
    estimate, reference = rigid_transform(estimate), rigid_transform(reference)
    error = np.linalg.solve(reference, estimate)
    phi = Rotation.from_matrix(error[:3, :3]).as_rotvec()
    theta = np.linalg.norm(phi)
    x, y, z = phi
    skew = np.array([[0, -z, y], [z, 0, -x], [-y, x, 0]])
    # Stable inverse left Jacobian, including the near-zero limit and pi.
    coefficient = (
        1 / 12 + theta**2 / 720
        if theta < 1e-4
        else (1 - theta / (2 * np.tan(theta / 2))) / theta**2
    )
    rho = (np.eye(3) - 0.5 * skew + coefficient * skew @ skew) @ error[:3, 3]
    return np.concatenate([rho, phi])


def pose_consistency(
    estimate, reference, residual_covariance=None, *, calibrated=False, confidence=0.99
):
    residual = pose_residual(estimate, reference)
    return {
        "residual_order": "rho_m_then_phi_rad",
        "residual_convention": "Log(inverse(reference) @ estimate)",
        "residual": residual.tolist(),
        "statistical_consistency": gaussian_consistency(
            residual, residual_covariance, calibrated=calibrated, confidence=confidence
        ),
    }
