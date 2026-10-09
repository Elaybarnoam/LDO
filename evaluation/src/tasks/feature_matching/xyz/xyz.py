"""Numerical per-correspondence XYZ checks. No image loading or matching."""
from dataclasses import dataclass
import time
import numpy as np

@dataclass(frozen=True)
class FeatureObservation:
    timestamp_ns: int
    feature_id: int
    pixel_xy: object
    camera_xyz: object = None
    covariance: object = None
    camera_pose: object = None
    depth_reason: str = None

def world_points(points, camera_pose):
    return points @ camera_pose[:3, :3].T + camera_pose[:3, 3]

def world_covariance(points, covariance, pose, policy):
    rotation = pose[:3, :3]
    rotated = points @ rotation.T
    skew = np.zeros((len(points), 3, 3))
    skew[:, 0, 1], skew[:, 0, 2] = -rotated[:, 2], rotated[:, 1]
    skew[:, 1, 0], skew[:, 1, 2] = rotated[:, 2], -rotated[:, 0]
    skew[:, 2, 0], skew[:, 2, 1] = -rotated[:, 1], rotated[:, 0]
    return rotation @ covariance @ rotation.T + np.eye(3)*policy["reference_position_sigma_m"]**2 + skew @ np.swapaxes(skew, 1, 2)*np.radians(policy["reference_orientation_sigma_degrees"])**2

def check_correspondence(query, historical, policy):
    started = time.perf_counter()
    result = {"query_feature_id": query.feature_id, "historical_feature_id": historical.feature_id,
              "query_timestamp_ns": query.timestamp_ns, "historical_timestamp_ns": historical.timestamp_ns,
              "query_feature_xy": list(query.pixel_xy), "historical_feature_xy": list(historical.pixel_xy),
              "verdict": "untestable", "reason": None,
              "query_depth_reason": query.depth_reason, "historical_depth_reason": historical.depth_reason}
    result["query_camera_xyz"] = np.asarray(query.camera_xyz).tolist() if query.camera_xyz is not None else None
    result["historical_camera_xyz"] = np.asarray(historical.camera_xyz).tolist() if historical.camera_xyz is not None else None
    result["query_camera_pose"] = np.asarray(query.camera_pose).tolist() if query.camera_pose is not None else None
    result["historical_camera_pose"] = np.asarray(historical.camera_pose).tolist() if historical.camera_pose is not None else None
    def finish(reason, verdict="untestable"):
        result.update(reason=reason, verdict=verdict, xyz_check_ms=(time.perf_counter()-started)*1000)
        return result
    if query.camera_pose is None or historical.camera_pose is None:
        return finish("reference_pose_unavailable")
    if query.depth_reason or historical.depth_reason or query.camera_xyz is None or historical.camera_xyz is None:
        return finish("reliable_stereo_depth_unavailable")
    try:
        q, h = np.asarray(query.camera_xyz, float).reshape(1,3), np.asarray(historical.camera_xyz, float).reshape(1,3)
        qc, hc = np.asarray(query.covariance, float).reshape(1,3,3), np.asarray(historical.covariance, float).reshape(1,3,3)
        qp, hp = np.asarray(query.camera_pose, float).reshape(4,4), np.asarray(historical.camera_pose, float).reshape(4,4)
        if not all(np.isfinite(v).all() for v in (q,h,qc,hc,qp,hp)) or q[0,2] <= 0 or h[0,2] <= 0:
            return finish("invalid_numerical_observation")
        if min(np.linalg.eigvalsh(qc)[0]) < -1e-10 or min(np.linalg.eigvalsh(hc)[0]) < -1e-10:
            return finish("invalid_depth_covariance")
        qw, hw = world_points(q,qp), world_points(h,hp)
        covariance = world_covariance(q,qc,qp,policy)[0]+world_covariance(h,hc,hp,policy)[0]
        np.linalg.cholesky(covariance)
        delta = (qw-hw)[0]
        score = float(delta @ np.linalg.solve(covariance,delta))
        if not np.isfinite(score): return finish("invalid_combined_uncertainty")
        result.update(query_camera_xyz=q[0].tolist(), historical_camera_xyz=h[0].tolist(),
            query_world_xyz=qw[0].tolist(), historical_world_xyz=hw[0].tolist(),
            xyz_error_m=float(np.linalg.norm(delta)), mahalanobis_squared=score,
            combined_world_covariance=covariance.tolist(),
            three_sigma_radius_m=float(3*np.sqrt(np.linalg.eigvalsh(covariance)[-1])))
        supported = score <= policy["stereo_world_mahalanobis_squared_maximum"]
        return finish("world_xyz_agrees" if supported else "world_xyz_disagrees", "supported" if supported else "contradicted")
    except (ValueError, np.linalg.LinAlgError, TypeError):
        return finish("invalid_numerical_observation")
