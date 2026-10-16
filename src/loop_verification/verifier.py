"""Deterministic shared verification policy over observation-only inputs."""

import numpy as np

from .acceptance import rejection_reason
from .configuration import fingerprint
from .contracts import VerificationInput, VerificationResult
from .pose_estimation import estimate


class LoopVerifier:
    def __init__(self, policy: dict):
        self.policy = dict(policy)
        self.fingerprint = fingerprint(self.policy)

    def verify(self, data: VerificationInput) -> VerificationResult:
        valid = np.flatnonzero(data.depth_valid)
        diagnostics = {
            "reported_matches": len(data.assignment_ids),
            "usable_points": len(valid),
            "verifier_fingerprint": self.fingerprint,
        }
        if len(valid) < self.policy["minimum_usable_points"]:
            return VerificationResult(
                "insufficient_evidence", "too_few_reliable_query_depths", None, (), diagnostics
            )
        points = data.query_camera_xyz[valid]
        singular = np.linalg.svd(points - points.mean(axis=0), compute_uv=False)
        if singular[1] / max(singular[0], 1e-15) < self.policy["minimum_second_axis_ratio"]:
            return VerificationResult(
                "rejected", "degenerate_object_geometry", None, (), diagnostics
            )
        seed = (self.policy["seed"] + data.query_timestamp_ns + data.historical_timestamp_ns) % (
            2**31 - 1
        )
        result = estimate(
            points,
            data.historical_pixels[valid],
            data.camera_matrix,
            data.distortion,
            seed,
            self.policy,
        )
        if result is None:
            return VerificationResult("rejected", "pose_estimation_failed", None, (), diagnostics)
        pose, inliers, numerical = result
        diagnostics.update(numerical)
        reason = rejection_reason(diagnostics, self.policy)
        ids = tuple(tuple(map(int, pair)) for pair in data.assignment_ids[valid[inliers]])
        pose.flags.writeable = False
        return VerificationResult(
            "rejected" if reason else "accepted",
            reason or "geometric_checks_passed",
            pose,
            ids,
            diagnostics,
        )
