"""TartanAir source adapter and detector-only grayscale replay export."""

import json
from pathlib import Path

import cv2
import numpy as np
import yaml

from tasks.loop_closure.comparison.reference import sha256, write_json

from .geometry import CV_TO_NED, backproject, camera_pose, decode_depth, sample_depth, visibility


def prepare_sequence(settings, trajectory, output, stride):
    source = Path(settings["root"]) / settings["environment"] / settings["difficulty"] / trajectory
    poses_path = source / "pose_lcam_front.txt"
    poses = np.loadtxt(poses_path)
    images = sorted((source / "image_lcam_front").glob("*.png"))
    if len(images) != len(poses):
        raise ValueError("Image/pose row alignment is incomplete")
    cam_times = np.load(source / "imu/cam_time.npy", allow_pickle=False).reshape(-1)
    if (
        len(cam_times) != len(images)
        or not np.isfinite(cam_times).all()
        or np.any(np.diff(cam_times) <= 0)
    ):
        raise ValueError("Camera timestamps differ from actual source frames")
    stamps = np.rint((cam_times - cam_times[0]) * 1e9).astype(np.int64) + 1_000_000_000
    output.mkdir(parents=True, exist_ok=False)
    cameras = (
        (("cam0", "lcam_front"),)
        if settings.get("reference_only")
        else (("cam0", "lcam_front"), ("cam1", "rcam_front"))
    )
    frame_rows = []
    for i in range(0, len(images), stride):
        if int(images[i].name.split("_")[0]) != i:
            raise ValueError("Source image indices are not contiguous")
        stamp = int(stamps[i])
        for camera, side in cameras:
            original = source / f"image_{side}" / f"{i:06d}_{side}.png"
            gray = cv2.imread(str(original), cv2.IMREAD_GRAYSCALE)
            if gray is None or gray.shape != (640, 640):
                raise ValueError("Source stereo image is missing or wrong sized")
            destination = output / "mav0" / camera / "data" / f"{stamp}.png"
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not cv2.imwrite(str(destination), gray):
                raise RuntimeError("Could not export detector replay image")
        depth = source / "depth_lcam_front" / f"{i:06d}_lcam_front_depth.png"
        decode_depth(depth)  # Fail before either model runs on malformed reference data.
        frame_rows.append(
            {
                "timestamp_ns": stamp,
                "source_index": i,
                "image": str(output / "mav0/cam0/data" / f"{stamp}.png"),
                "right_image": str(output / "mav0/cam1/data" / f"{stamp}.png")
                if len(cameras) == 2
                else None,
                "depth": str(depth),
                "pose": camera_pose(poses[i]).tolist(),
                "image_sha256": sha256(output / "mav0/cam0/data" / f"{stamp}.png"),
                "depth_sha256": sha256(depth),
                "right_image_sha256": sha256(output / "mav0/cam1/data" / f"{stamp}.png")
                if len(cameras) == 2
                else None,
                "source_image_sha256": sha256(images[i]),
            }
        )
    for camera, offset in (
        (("cam0", 0.0),) if len(cameras) == 1 else (("cam0", 0.0), ("cam1", 0.25))
    ):
        directory = output / "mav0" / camera
        t = np.eye(4)
        t[:3, :3] = CV_TO_NED
        t[1, 3] = offset
        sensor = {
            "camera_model": "pinhole",
            "distortion_model": "radial-tangential",
            "intrinsics": [320.0, 320.0, 319.5, 319.5],
            "resolution": [640, 640],
            "distortion_coefficients": [0.0, 0.0, 0.0, 0.0],
            "T_BS": {"rows": 4, "cols": 4, "data": t.ravel().tolist()},
        }
        (directory / "sensor.yaml").write_text(yaml.safe_dump(sensor))
        (directory / "data.csv").write_text(
            "#timestamp,filename\n"
            + "".join(f"{f['timestamp_ns']},{f['timestamp_ns']}.png\n" for f in frame_rows)
        )
    (output / "replay.tsv").write_text(
        "".join(f"{f['timestamp_ns']}\t{f['image']}\n" for f in frame_rows)
    )
    write_json(output / "frames.json", frame_rows)
    return {
        "trajectory": trajectory,
        "frames": len(frame_rows),
        "source_frames": len(images),
        "pose_sha256": sha256(poses_path),
        "frames_sha256": sha256(output / "frames.json"),
        "camera_times_sha256": sha256(source / "imu/cam_time.npy"),
        "replay_inputs_sha256": {
            str(p.relative_to(output)): sha256(p) for p in output.glob("mav0/cam*/*") if p.is_file()
        },
        "imu_acc_sha256": sha256(source / "imu/acc.npy"),
        "imu_gyro_sha256": sha256(source / "imu/gyro.npy"),
        "root": str(output),
        "source": str(source),
        "inputs": "identical_grayscale_cam0; reference_only"
        if len(cameras) == 1
        else "identical_grayscale_stereo; detectors_currently_use_cam0_only",
        "reference_data_are_detector_inputs": False,
    }


def frames(root):
    with (root / "frames.json").open() as stream:
        return json.load(stream)


def audit_stereo(settings, trajectory, policy):
    """Audit source calibration against right-camera reference, never detector outputs."""
    source = Path(settings["root"]) / settings["environment"] / settings["difficulty"] / trajectory
    left = np.loadtxt(source / "pose_lcam_front.txt")
    right = np.loadtxt(source / "pose_rcam_front.txt")
    if left.shape != right.shape:
        raise ValueError("Left/right reference pose alignment differs")
    expected = np.eye(4)
    expected[0, 3] = -0.25
    errors = [
        float(
            np.max(np.abs(np.linalg.inv(camera_pose(right_row)) @ camera_pose(left_row) - expected))
        )
        for left_row, right_row in zip(left, right, strict=True)
    ]
    if max(errors) > 1e-4:
        raise ValueError("Source stereo pose differs from frozen 25 cm calibration")
    depth = decode_depth(source / "depth_lcam_front/000000_lcam_front_depth.png")
    target = decode_depth(source / "depth_rcam_front/000000_rcam_front_depth.png")
    xx, yy = np.meshgrid(np.arange(24, 616, 24), np.arange(24, 616, 24))
    pixels = np.column_stack([xx.ravel(), yy.ravel()])
    z, valid = sample_depth(depth, pixels, policy)
    projected, visible = visibility(backproject(pixels, z), target, expected, policy)
    _, target_valid = sample_depth(target, projected, policy)
    usable = valid & target_valid & (projected[:, 0] >= 1) & (projected[:, 0] < 639)
    fraction = float(np.mean(visible[usable])) if usable.any() else None
    if fraction is None or fraction < 0.8:
        raise ValueError(f"Stereo reference consistency audit failed: {fraction}")
    return {
        "maximum_pose_calibration_error": max(errors),
        "reference_depth_consistency_fraction": fraction,
        "reference_depth_tested_points": int(usable.sum()),
        "right_pose_sha256": sha256(source / "pose_rcam_front.txt"),
    }
