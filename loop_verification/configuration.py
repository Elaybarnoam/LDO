"""Strict operational policy independent from offline assessment tolerances."""

import hashlib
import json
from pathlib import Path

import numpy as np
import yaml


def fingerprint(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def load_policy(path: Path) -> dict:
    policy = yaml.safe_load(path.read_text(encoding="utf-8"))
    expected = {
        "version",
        "seed",
        "minimum_usable_points",
        "minimum_inliers",
        "minimum_inlier_ratio",
        "ransac_error_px",
        "maximum_median_error_px",
        "maximum_p95_error_px",
        "ransac_iterations",
        "ransac_confidence",
        "minimum_cheirality_ratio",
        "minimum_second_axis_ratio",
        "maximum_pose_condition",
    }
    if not isinstance(policy, dict) or set(policy) != expected or policy["version"] != 1:
        raise ValueError("Invalid operational verifier policy")
    for key in expected - {"version"}:
        if (
            type(policy[key]) not in (int, float)
            or not np.isfinite(policy[key])
            or policy[key] < (0 if key == "seed" else 1e-15)
        ):
            raise ValueError(f"Invalid operational parameter: {key}")
    for key in ("seed", "minimum_usable_points", "minimum_inliers", "ransac_iterations"):
        if type(policy[key]) is not int:
            raise ValueError(f"Expected integer: {key}")
    if (
        min(policy["minimum_usable_points"], policy["minimum_inliers"]) < 6
        or policy["seed"] >= 2**31
    ):
        raise ValueError("Invalid PnP point budget or seed")
    for key in (
        "minimum_inlier_ratio",
        "ransac_confidence",
        "minimum_cheirality_ratio",
        "minimum_second_axis_ratio",
    ):
        if not 0 < policy[key] <= 1:
            raise ValueError(f"Invalid ratio: {key}")
    if policy["ransac_confidence"] == 1:
        raise ValueError("RANSAC confidence must be less than one")
    return policy
