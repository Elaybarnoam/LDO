"""Exported upstream ORB correspondences tested against reference camera geometry."""

from .orb_features import read_features
from collections import OrderedDict
import hashlib
from pathlib import Path

import cv2
import numpy as np
import yaml


def reference_errors(query_points, historical_points, camera_matrix, relative_pose, minimum_translation):
    """Pixel Sampson error for x_h^T F_hq x_q; rotation reprojection near zero baseline."""
    rotation, translation = relative_pose[:3, :3], relative_pose[:3, 3]
    query = np.column_stack((query_points, np.ones(len(query_points))))
    historical = np.column_stack((historical_points, np.ones(len(historical_points))))
    inverse_k = np.linalg.inv(camera_matrix)
    if np.linalg.norm(translation) < minimum_translation:
        predicted = (camera_matrix @ rotation @ inverse_k @ query.T).T
        valid = predicted[:, 2] > 1e-9
        errors = np.full(len(query), np.inf)
        errors[valid] = np.linalg.norm(predicted[valid, :2]/predicted[valid, 2:] - historical_points[valid], axis=1)
        return errors, "reference_rotation_reprojection"
    translation = translation / np.linalg.norm(translation)
    x, y, z = translation
    skew = np.array([[0, -z, y], [z, 0, -x], [-y, x, 0]])
    fundamental = inverse_k.T @ skew @ rotation @ inverse_k
    lines_h = query @ fundamental.T
    lines_q = historical @ fundamental
    residual = np.sum(historical * lines_h, axis=1)
    denominator = np.sum(lines_h[:, :2]**2, axis=1) + np.sum(lines_q[:, :2]**2, axis=1)
    errors = np.full(len(query), np.inf)
    valid = denominator > 1e-15
    errors[valid] = np.abs(residual[valid]) / np.sqrt(denominator[valid])
    return errors, "reference_epipolar_sampson"


def coverage(points, width, height):
    if not len(points):
        return 0.0
    cells = np.floor(points / np.array([width, height]) * 4).astype(int)
    cells = np.clip(cells, 0, 3)
    return len(set(map(tuple, cells))) / 16


def classify(measurements, policy):
    if not measurements["reference_pose_available"]:
        return "inconclusive", ["reference_pose_unavailable"]
    if measurements["match_count"] < policy["minimum_matches"]:
        return "inconclusive", ["insufficient_independent_matches"]
    if (measurements["reference_inliers"] >= policy["minimum_inliers"] and
            measurements["reference_inlier_ratio"] >= policy["minimum_inlier_ratio"]):
        return "overlap_supported", ["matches_consistent_with_reference_pose"]
    if (measurements["homography_inliers"] >= policy["minimum_inliers"] and
            measurements["reference_inlier_ratio"] <= policy["contradiction_maximum_inlier_ratio"]):
        return "suspicious", ["visual_pattern_matches_but_reference_geometry_disagrees"]
    return "inconclusive", ["insufficient_or_ambiguous_geometric_evidence"]


class ImageGeometry:
    correspondence_source = None

    def __init__(self, sequence, policy, feature_root=None, correspondence_source=None):
        self.policy = policy
        self.correspondence_source = correspondence_source
        self.feature_root = Path(feature_root) if feature_root else Path(sequence) / "orb_features"
        self.cache = OrderedDict()
        calibration = yaml.safe_load((Path(sequence) / "mav0/cam0/sensor.yaml").read_text())
        if calibration["camera_model"] != "pinhole" or calibration["distortion_model"] != "radial-tangential":
            raise ValueError("Candidate checker currently supports EuRoC pinhole cam0 only")
        fx, fy, cx, cy = calibration["intrinsics"]
        self.k = np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1]], dtype=float)
        self.distortion = np.array(calibration["distortion_coefficients"], dtype=float)
        self.resolution = tuple(calibration["resolution"])
        cv2.setNumThreads(1)
        self.matcher = cv2.BFMatcher(cv2.NORM_HAMMING)

    def features(self, path):
        path = Path(path)
        if path in self.cache:
            self.cache.move_to_end(path)
            return self.cache[path]
        raw = path.read_bytes()
        image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_GRAYSCALE)
        if image is None or image.shape[::-1] != self.resolution:
            raise ValueError(f"Missing/corrupt image or unexpected size: {path}")
        points, descriptors, size = (self.correspondence_source.features(path) if self.correspondence_source is not None
                                     else read_features(self.feature_root, path))
        if size != image.shape[::-1]:
            raise ValueError("Feature export resolution differs from image")
        undistorted = cv2.undistortPoints(points.reshape(-1, 1, 2), self.k, self.distortion, P=self.k).reshape(-1, 2) if len(points) else points
        data = {"points": points, "undistorted": undistorted, "descriptors": descriptors,
                "sha256": hashlib.sha256(raw).hexdigest()}
        self.cache[path] = data
        while len(self.cache) > self.policy["feature_cache_size"]:
            self.cache.popitem(last=False)
        return data

    def mutual_matches(self, qd, hd):
        if qd is None or hd is None or len(qd) < 2 or len(hd) < 2:
            return []
        def ratio_pairs(a, b):
            return {(m.queryIdx, m.trainIdx): m for pair in self.matcher.knnMatch(a, b, k=2)
                    if len(pair) == 2 for m, n in [pair] if m.distance < self.policy["match_ratio"] * n.distance}
        forward, backward = ratio_pairs(qd, hd), ratio_pairs(hd, qd)
        return [match for pair, match in forward.items() if pair[::-1] in backward]

    def check(self, query_path, historical_path, relative_pose, seed, on_matches=None):
        query, historical = self.features(query_path), self.features(historical_path)
        qd, hd = query["descriptors"], historical["descriptors"]
        match_metadata = {}
        if self.correspondence_source is None:
            matches = self.mutual_matches(qd, hd)
        else:
            matches, match_metadata = self.correspondence_source.assignments(
                Path(query_path), Path(historical_path), len(query["points"]), len(historical["points"]))
        raw_matches = matches
        ransac = {"status": "disabled_feature_evaluation", "raw_match_count": len(matches),
                  "retained_match_count": len(matches), "rejected_match_count": 0}
        qi = [match.queryIdx for match in matches]
        hi = [match.trainIdx for match in matches]
        qp, hp = query["undistorted"][qi], historical["undistorted"][hi]
        width, height = self.resolution
        homography_inliers = 0
        if len(matches) >= 4:
            cv2.setRNGSeed(seed)
            model, mask = cv2.findHomography(qp, hp, cv2.RANSAC, self.policy["homography_error_px"], maxIters=2000, confidence=.999)
            if model is not None and mask is not None:
                mask = mask.ravel().astype(bool)
                homography_inliers = int(mask.sum())
        reference_inliers, method, median = 0, None, None
        if relative_pose is not None and len(matches):
            errors, method = reference_errors(qp, hp, self.k, relative_pose, self.policy["minimum_translation_m"])
            mask = errors <= self.policy["ground_truth_error_px"]
            reference_inliers = int(mask.sum())
            finite = errors[np.isfinite(errors)]
            median = float(np.median(finite)) if len(finite) else None
        measurement = {"reference_pose_available": relative_pose is not None, "match_count": len(matches), "raw_match_count": len(raw_matches),
                       "query_features": len(query["points"]), "historical_features": len(historical["points"]),
                       "reference_method": method, "reference_inliers": reference_inliers,
                       "reference_inlier_ratio": reference_inliers / len(matches) if matches else 0.0,
                       "reference_median_error_px": median,
                       "homography_inliers": homography_inliers,
                       "query_image_sha256": query["sha256"], "historical_image_sha256": historical["sha256"]}
        status, reasons = classify(measurement, self.policy)
        result = {"outcome": status, "reasons": reasons, "measurements": measurement, "accuracy_label": None, "ransac": ransac,
                  "feature_matches": [{"query_feature_id": m.queryIdx, "historical_feature_id": m.trainIdx,
                     "query_feature_xy": query["points"][m.queryIdx].tolist(),
                     "historical_feature_xy": historical["points"][m.trainIdx].tolist(),
                     "hamming_distance": m.distance} for m in matches]}
        if on_matches is not None:
            result["stereo"] = on_matches(matches)
        if self.correspondence_source is not None:
            # Provenance only: preserve the exact numerical checks and verdicts.
            result["measurements"]["feature_source"] = self.correspondence_source.source
            for item in result["feature_matches"] + result.get("stereo", {}).get("feature_results", []):
                item.pop("hamming_distance", None)
                item.update(match_metadata[(item["query_feature_id"], item["historical_feature_id"])])
        return result
