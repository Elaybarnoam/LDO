"""Shared decision rules; failure reasons are not ground-truth labels."""


def rejection_reason(diagnostics: dict, policy: dict) -> str | None:
    rules = (
        (diagnostics["inliers"] < policy["minimum_inliers"], "too_few_inliers"),
        (diagnostics["inlier_ratio"] < policy["minimum_inlier_ratio"], "low_inlier_ratio"),
        (diagnostics["cheirality_ratio"] < policy["minimum_cheirality_ratio"], "cheirality_failed"),
        (
            diagnostics["median_error_px"] > policy["maximum_median_error_px"],
            "median_reprojection_error",
        ),
        (diagnostics["p95_error_px"] > policy["maximum_p95_error_px"], "p95_reprojection_error"),
        (diagnostics["pose_condition"] > policy["maximum_pose_condition"], "ill_conditioned_pose"),
    )
    return next((reason for failed, reason in rules if failed), None)
