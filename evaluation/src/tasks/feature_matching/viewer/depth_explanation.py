"""Explain saved stereo abstentions without inferring a new feature verdict."""


def stereo_details(point: dict, pair: dict, role: str, policy: dict) -> list[str]:
    reason = point.get(f"{role}_depth_reason")
    explanations = {
        "low_stereo_parallax": f"Parallax below {policy['stereo_minimum_parallax_degrees']:.2f} deg",
        "uncertain_stereo_depth": f"Depth sigma / depth > {100 * policy['stereo_maximum_relative_depth_sigma']:.0f}%",
        "stereo_left_right_inconsistent": f"Left/right error > {policy['stereo_lr_max_error_px']:.1f} px or invalid",
        "depth_out_of_range": f"Depth outside {policy['stereo_minimum_depth_m']:.2f}-{policy['stereo_maximum_depth_m']:.0f} m",
        "stereo_reprojection_error": f"Stereo projection error > {policy['stereo_maximum_reprojection_px']:.1f} px",
        "rectified_observation_outside_canvas": "Observation outside rectified canvas",
        "rectified_observation_outside_sensor_content": "Observation maps to sensor padding",
        "stereo_correspondence_outside_sensor_content": "Right correspondence maps to padding",
        "stereo_occluded_or_outside_image": "Right projection outside stereo image",
        "dense_disparity_invalid": "Predicted disparity invalid or <= 0",
    }
    matching = pair.get("stereo", {}).get("frames", {}).get(role, {}).get("matching", {})
    recovered = point[f"{role}_feature_id"] in matching.get("recovered_feature_ids", [])
    source = "Full-field recovery" if recovered else "Primary stereo"
    xyz = point.get(f"{role}_camera_xyz")
    location = f"Depth Z: {xyz[2]:.3f} m" if xyz else "No reliable camera XYZ"
    return [
        explanations.get(
            reason, reason.replace("_", " ") if reason else "Depth reliability gates passed"
        ),
        location,
        f"Source: {source}",
        f"Pixel sigma: {policy['stereo_pixel_sigma_px']:.1f} px (assumed)",
        "Unknown is not a mismatch" if reason else "Ready for world XYZ comparison",
    ]
