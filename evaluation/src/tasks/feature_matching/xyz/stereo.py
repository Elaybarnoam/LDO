"""Independent calibrated stereo XYZ and reference-world consistency.

Uses raw camera frames with normalized triangulation, so no rectification
rotation is accidentally mixed with the original camera/body extrinsics.
Covariance is a first-order noise model, not measured ground-truth accuracy.
"""

import csv
import hashlib
import math
import time
from collections import Counter, OrderedDict
from pathlib import Path

import cv2
import numpy as np
import yaml

from .coverage import summarize_coverage
from .poses import sensor_transform
from .xyz import FeatureObservation, check_correspondence, world_covariance, world_points


def camera_parameters(path):
    sensor = yaml.safe_load(Path(path).read_text())
    if sensor["camera_model"] != "pinhole" or sensor["distortion_model"] != "radial-tangential":
        raise ValueError("Stereo checker requires calibrated pinhole cameras")
    fx, fy, cx, cy = sensor["intrinsics"]
    return (
        np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1]], dtype=float),
        np.array(sensor["distortion_coefficients"], dtype=float),
        tuple(sensor["resolution"]),
    )


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


def compare_landmarks(qxyz, hxyz, qcov, hcov, qpose, hpose, qp, hp, k, distortion, policy):
    qw, hw = world_points(qxyz, qpose), world_points(hxyz, hpose)
    delta = qw - hw
    covariance = world_covariance(qxyz, qcov, qpose, policy) + world_covariance(
        hxyz, hcov, hpose, policy
    )
    mahalanobis_squared = np.einsum(
        "ni,ni->n", delta, np.linalg.solve(covariance, delta[..., None])[..., 0]
    )
    q_from_h = (hw - qpose[:3, 3]) @ qpose[:3, :3]
    h_from_q = (qw - hpose[:3, 3]) @ hpose[:3, :3]
    positive = (q_from_h[:, 2] > 0) & (h_from_q[:, 2] > 0)
    reprojection = np.full((len(qxyz), 2), np.inf)
    if positive.any():
        reprojection[positive, 0] = np.linalg.norm(
            project(q_from_h[positive], k, distortion) - qp[positive], axis=1
        )
        reprojection[positive, 1] = np.linalg.norm(
            project(h_from_q[positive], k, distortion) - hp[positive], axis=1
        )
    accepted = (
        positive
        & (mahalanobis_squared <= policy["stereo_world_mahalanobis_squared_maximum"])
        & (reprojection.max(axis=1) <= policy["stereo_cross_reprojection_px"])
    )
    return {
        "query_world_xyz": qw,
        "historical_world_xyz": hw,
        "xyz_error_m": np.linalg.norm(delta, axis=1),
        "mahalanobis_squared": mahalanobis_squared,
        "three_sigma_radius_m": 3 * np.sqrt(np.linalg.eigvalsh(covariance)[:, -1]),
        "cross_reprojection_px": reprojection,
        "accepted": accepted,
    }


class StereoGeometry:
    def __init__(self, sequence, image_geometry, policy):
        self.sequence, self.geometry, self.policy = Path(sequence), image_geometry, policy
        self.cache = OrderedDict()
        self.dense = None
        folder = self.sequence / "mav0/cam1"
        self.available = (folder / "sensor.yaml").is_file() and (folder / "data.csv").is_file()
        self.unavailable_reason = "right_camera_calibration_or_index_missing"
        if not self.available:
            return
        self.k0, self.d0, self.size0 = camera_parameters(self.sequence / "mav0/cam0/sensor.yaml")
        self.k1, self.d1, self.size1 = camera_parameters(folder / "sensor.yaml")
        self.right_from_left = np.linalg.inv(
            sensor_transform(folder / "sensor.yaml")
        ) @ sensor_transform(self.sequence / "mav0/cam0/sensor.yaml")
        if np.linalg.norm(self.right_from_left[:3, 3]) < 1e-6:
            raise ValueError("Stereo baseline is zero")
        if policy["stereo_backend"] == "fast_foundationstereo":
            from .dense_stereo import DenseStereo

            self.dense = DenseStereo(
                policy,
                self.k0,
                self.d0,
                self.k1,
                self.d1,
                self.size0,
                self.right_from_left,
                self.geometry.feature_root.parent / "stereo_correspondences",
            )
        self.right_images = {}
        with (folder / "data.csv").open() as stream:
            for row in csv.reader(stream):
                if not row or row[0].startswith("#"):
                    continue
                name = row[1].strip()
                if Path(name).name != name:
                    raise ValueError("Unsafe cam1 image filename")
                stamp = int(row[0])
                if stamp in self.right_images:
                    raise ValueError("Duplicate cam1 timestamp")
                self.right_images[stamp] = folder / "data" / name

    def frame(self, stamp, left_path, left):
        if stamp in self.cache:
            self.cache.move_to_end(stamp)
            return self.cache[stamp]
        right_path = self.right_images.get(stamp)
        if right_path is None or not right_path.is_file():
            return {"available": False, "reason": "synchronized_right_image_missing"}
        raw = right_path.read_bytes()
        image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_GRAYSCALE)
        if image is None or image.shape[::-1] != self.size1:
            raise ValueError(f"Corrupt/unexpected cam1 image: {right_path}")
        matching_evidence = {"backend": "orb_mutual"}
        association_reasons = []
        if self.dense is not None:
            right_points, associated, association_reasons, matching_evidence = self.dense.match(
                stamp, left_path, right_path, left["points"]
            )
            li = np.flatnonzero(associated).tolist()
            right_matched = right_points[li]
        else:
            from .orb_features import read_features

            right_points, descriptors, size = read_features(self.geometry.feature_root, right_path)
            if size != self.size1:
                raise ValueError("Right ORB export resolution differs from calibration")
            pairs = self.geometry.mutual_matches(left["descriptors"], descriptors)
            li, ri = [m.queryIdx for m in pairs], [m.trainIdx for m in pairs]
            right_matched = right_points[ri]
        xyz, covariance, reliable, rejected = reconstruct(
            left["points"][li],
            right_matched,
            self.k0,
            self.d0,
            self.k1,
            self.d1,
            self.right_from_left,
            self.policy,
        )
        lookup = {index: i for i, index in enumerate(li) if reliable[i]}
        reasons_by_id = {
            i: (
                association_reasons[i]
                if association_reasons
                else "stereo_correspondence_unavailable"
            )
            for i in range(len(left["points"]))
        }
        for j, i in enumerate(li):
            reasons_by_id[i] = None if reliable[j] else rejected[j]
        result = {
            "available": True,
            "depth_reasons": reasons_by_id,
            "lookup": lookup,
            "xyz": xyz,
            "covariance": covariance,
            "stereo_matches": len(li),
            "matching": matching_evidence,
            "association_rejection_reasons": dict(Counter(r for r in association_reasons if r)),
            "reliable_depths": len(lookup),
            "rejection_reasons": dict(Counter(reason for reason in rejected if reason)),
            "right_image": str(right_path),
            "right_image_sha256": hashlib.sha256(raw).hexdigest(),
            "left_image_sha256": left["sha256"],
        }
        self.cache[stamp] = result
        while len(self.cache) > self.policy["feature_cache_size"]:
            self.cache.popitem(last=False)
        return result

    def close(self):
        if self.dense is not None:
            self.dense.close()

    def check(
        self, query_stamp, historical_stamp, query_path, historical_path, matches, qpose, hpose
    ):
        started = time.perf_counter()
        evidence = self._check_geometry(
            query_stamp, historical_stamp, query_path, historical_path, matches, qpose, hpose
        )
        preparation_ms = (time.perf_counter() - started) * 1000
        q, h = self.geometry.features(query_path), self.geometry.features(historical_path)
        qs = (
            self.frame(query_stamp, query_path, q)
            if self.available
            else {"available": False, "reason": self.unavailable_reason}
        )
        hs = (
            self.frame(historical_stamp, historical_path, h)
            if self.available
            else {"available": False, "reason": self.unavailable_reason}
        )
        diagnostics = {
            (p["query_feature_id"], p["historical_feature_id"]): p
            for p in evidence.get("landmarks", [])
        }

        def observation(stamp, feature_id, features, frame, pose):
            index = frame.get("lookup", {}).get(feature_id)
            reason = (
                frame.get("reason")
                if not frame.get("available")
                else frame.get("depth_reasons", {}).get(feature_id)
            )
            if index is None:
                reason = reason or "reliable_depth_unavailable"
            return FeatureObservation(
                stamp,
                feature_id,
                features["points"][feature_id],
                frame["xyz"][index] if index is not None else None,
                frame["covariance"][index] if index is not None else None,
                pose,
                reason,
            )

        results = []
        qmatching, hmatching = qs.get("matching", {}), hs.get("matching", {})
        domain_known = (
            "primary_outside_feature_ids" in qmatching
            and "primary_outside_feature_ids" in hmatching
        )
        qoutside = set(qmatching.get("primary_outside_feature_ids", []))
        houtside = set(hmatching.get("primary_outside_feature_ids", []))
        for match in matches:
            qobs = observation(query_stamp, match.queryIdx, q, qs, qpose)
            hobs = observation(historical_stamp, match.trainIdx, h, hs, hpose)
            result = check_correspondence(qobs, hobs, self.policy)
            if domain_known:
                result.update(
                    query_primary_rectified_domain=match.queryIdx not in qoutside,
                    historical_primary_rectified_domain=match.trainIdx not in houtside,
                )
            diagnostic = diagnostics.get((match.queryIdx, match.trainIdx), {})
            result["cross_reprojection_px"] = diagnostic.get("cross_reprojection_px")
            result["hamming_distance"] = match.distance
            result["query_depth_covariance"] = (
                qobs.covariance.tolist() if qobs.covariance is not None else None
            )
            result["historical_depth_covariance"] = (
                hobs.covariance.tolist() if hobs.covariance is not None else None
            )
            results.append(result)
        counts = {
            v: sum(p["verdict"] == v for p in results)
            for v in ("supported", "contradicted", "untestable")
        }
        testable = counts["supported"] + counts["contradicted"]
        evidence.update(
            feature_results=results,
            feature_counts=counts,
            coverage_breakdown=summarize_coverage(results),
            testable_correspondences=testable,
            reported_correspondences=len(matches),
            contradiction_rate=counts["contradicted"] / testable if testable else None,
            evaluation_coverage=testable / len(matches) if matches else None,
            timings_ms={
                "stereo_preparation_and_reprojection": preparation_ms,
                "xyz_checks": sum(p["xyz_check_ms"] for p in results),
            },
        )
        return evidence

    def _check_geometry(
        self, query_stamp, historical_stamp, query_path, historical_path, matches, qpose, hpose
    ):
        if not self.available:
            return {
                "available": False,
                "reason": self.unavailable_reason,
                "paired_landmarks": 0,
                "landmarks": [],
            }
        q, h = self.geometry.features(query_path), self.geometry.features(historical_path)
        qs, hs = (
            self.frame(query_stamp, query_path, q),
            self.frame(historical_stamp, historical_path, h),
        )
        frames = {
            "query": {
                key: value
                for key, value in qs.items()
                if key not in {"lookup", "xyz", "covariance", "depth_reasons"}
            },
            "historical": {
                key: value
                for key, value in hs.items()
                if key not in {"lookup", "xyz", "covariance", "depth_reasons"}
            },
        }
        if not qs["available"] or not hs["available"]:
            return {
                "available": False,
                "reason": "synchronized_right_image_missing",
                "frames": frames,
                "paired_landmarks": 0,
                "landmarks": [],
            }
        valid = [m for m in matches if m.queryIdx in qs["lookup"] and m.trainIdx in hs["lookup"]]
        base = {
            "reported_match_count": len(matches),
            "required_support_matches": math.ceil(
                len(matches) * self.policy["minimum_inlier_ratio"]
            ),
            "depth_availability_ratio": len(valid) / len(matches) if matches else 0.0,
            "available": True,
            "frames": frames,
            "paired_landmarks": len(valid),
            "consistent_landmarks": 0,
            "consistent_ratio": 0.0,
            "landmarks": [],
            "xyz_median_error_m": None,
            "cross_reprojection_median_px": None,
        }
        if qpose is None or hpose is None:
            return {**base, "reference_pose_available": False}
        base["reference_pose_available"] = True
        if not valid:
            return base
        qi, hi = [m.queryIdx for m in valid], [m.trainIdx for m in valid]
        q_indices = [qs["lookup"][i] for i in qi]
        h_indices = [hs["lookup"][i] for i in hi]
        compared = compare_landmarks(
            qs["xyz"][q_indices],
            hs["xyz"][h_indices],
            qs["covariance"][q_indices],
            hs["covariance"][h_indices],
            qpose,
            hpose,
            q["points"][qi],
            h["points"][hi],
            self.k0,
            self.d0,
            self.policy,
        )
        accepted = compared["accepted"]
        base.update(
            consistent_landmarks=int(accepted.sum()),
            consistent_ratio=int(accepted.sum()) / len(matches) if matches else 0.0,
            depth_valid_agreement_ratio=float(accepted.mean()),
            xyz_median_error_m=float(np.median(compared["xyz_error_m"])),
        )
        finite_reprojection = compared["cross_reprojection_px"][
            np.isfinite(compared["cross_reprojection_px"])
        ]
        base["cross_reprojection_median_px"] = (
            float(np.median(finite_reprojection)) if len(finite_reprojection) else None
        )
        for index, match in enumerate(valid):
            cross = compared["cross_reprojection_px"][index]
            base["landmarks"].append(
                {
                    "query_feature_id": match.queryIdx,
                    "historical_feature_id": match.trainIdx,
                    "query_feature_xy": q["points"][match.queryIdx].tolist(),
                    "historical_feature_xy": h["points"][match.trainIdx].tolist(),
                    "query_camera_xyz": qs["xyz"][q_indices[index]].tolist(),
                    "historical_camera_xyz": hs["xyz"][h_indices[index]].tolist(),
                    "query_world_xyz": compared["query_world_xyz"][index].tolist(),
                    "historical_world_xyz": compared["historical_world_xyz"][index].tolist(),
                    "xyz_error_m": float(compared["xyz_error_m"][index]),
                    "mahalanobis_squared": float(compared["mahalanobis_squared"][index]),
                    "three_sigma_radius_m": float(compared["three_sigma_radius_m"][index]),
                    "cross_reprojection_px": [
                        float(value) if np.isfinite(value) else None for value in cross
                    ],
                    "consistent": bool(accepted[index]),
                }
            )
        return base


def classify_stereo(stereo, policy):
    if not stereo.get("available"):
        return "inconclusive", [stereo.get("reason", "stereo_unavailable")]
    if not stereo.get("reference_pose_available"):
        return "inconclusive", ["reference_pose_unavailable"]
    total = stereo["reported_match_count"]
    required = math.ceil(total * policy["minimum_inlier_ratio"])
    if not total or stereo["paired_landmarks"] < required:
        return "inconclusive", ["insufficient_reliable_stereo_landmarks"]
    if stereo["consistent_landmarks"] >= required:
        return "overlap_supported", ["stereo_landmarks_agree_in_reference_world"]
    if (
        stereo["consistent_landmarks"] / stereo["paired_landmarks"]
        <= policy["contradiction_maximum_inlier_ratio"]
    ):
        return "suspicious", [
            "reliable_stereo_landmarks_disagree_in_reference_world_or_reprojection"
        ]
    return "inconclusive", ["ambiguous_stereo_world_consistency"]
