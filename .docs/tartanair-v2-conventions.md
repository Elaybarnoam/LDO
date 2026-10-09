# TartanAir V2 geometry conventions

Verified 2026-10-09 against official `castacks/tartanairpy` commit `158a6844d782942110967325ca3082f50ab2bfc7`. These rules apply to raw pinhole front images; customized fisheye/panorama depth is a different representation and must not share this reader implicitly.

## Camera-to-world transform

Pose rows are `[tx,ty,tz,qx,qy,qz,qw]`. The orientation rotates the local forward/right/down camera frame into the dataset world. For an OpenCV right/down/forward camera vector, use:

```text
C = [[0,0,1],
     [1,0,0],
     [0,1,0]]
R_world_opencv = Rotation.from_quat(row[3:7]).as_matrix() @ C
t_world_opencv = row[:3]
p_world = R_world_opencv @ p_opencv + t_world_opencv
```

Do not conjugate both sides unless intentionally changing the world coordinate system too. This directly reproduces the official flow sampling transform. The flow sampler sets `fx=fy=320`, `cx=cy=319.5` for integer-index pixel coordinates. [Pinned customizer source, lines 576–607](https://github.com/castacks/tartanairpy/blob/158a6844d782942110967325ca3082f50ab2bfc7/tartanair/customizer.py#L576)

## Pixel centers and depth

Raw pinhole depth is axial camera Z in metres, not Euclidean ray range:

```text
p_opencv = depth * [(u-319.5)/320, (v-319.5)/320, 1]
```

The official point-cloud example instead uses `u=index+0.5`, `v=index+0.5`, `cx=cy=320`; these conventions are equivalent. That example constructs NED-local points as `[depth,x_image,y_image]`. [Pinned point-cloud example](https://github.com/castacks/tartanairpy/blob/158a6844d782942110967325ca3082f50ab2bfc7/examples/accumulate_pointcloud.py#L31)

The flow code assigns point Z directly from depth and separately converts Z-depth to ray norm for visibility checks. [Pinned geometry code](https://github.com/castacks/tartanairpy/blob/158a6844d782942110967325ca3082f50ab2bfc7/tartanair/flow_calculation.py#L364)

## PNG decoding

```python
packed = cv2.imread(path, cv2.IMREAD_UNCHANGED)
depth = packed.view('<f4').squeeze(axis=-1)
```

Expect four uint8 bytes per pixel. Preserve bytes exactly: no RGB/BGR conversion, intensity scaling or grayscale load. The official reader reinterprets the OpenCV-loaded bytes directly and distinguishes `read_depth` from `read_dist` (which multiplies by ray norm). [Pinned reader](https://github.com/castacks/tartanairpy/blob/158a6844d782942110967325ca3082f50ab2bfc7/tartanair/reader.py#L42)

## File layout and archive limits

Verified consumer layout:

```text
ArchVizTinyHouseDay/Data_easy/<trajectory>/
  pose_lcam_front.txt
  pose_rcam_front.txt
  image_lcam_front/000000_lcam_front.png
  image_rcam_front/000000_rcam_front.png
  depth_lcam_front/000000_lcam_front_depth.png
  depth_rcam_front/000000_rcam_front_depth.png
  imu/acc.npy
  imu/gyro.npy
```

The official archive index lists `ArchVizTinyHouseDay/Data_easy/image_lcam_front.zip`, `image_rcam_front.zip`, `depth_lcam_front.zip`, `depth_rcam_front.zip` and `imu.zip`. It does not list a separate pose ZIP in that section. **Which ZIP embeds pose files must be verified from actual ZIP members**, rather than inferred from the downloader. Trajectory IDs must likewise be enumerated from the archive. [Pinned archive index](https://github.com/castacks/tartanairpy/blob/158a6844d782942110967325ca3082f50ab2bfc7/tartanair/download_files.txt#L928)

The official bundled cacher reads `imu/acc.npy`, `imu/gyro.npy`, concatenates acceleration then angular rate, and expects ten samples per image interval with `(N-1)*10` real samples. Its final ten zero-padding samples are a loader convenience, not measurements. [Pinned cacher](https://github.com/Amigoshan/data_cacher/blob/50d89654c5a5bd76d341b6c7e60afe740b435a39/modality_type/tartanair_types.py#L16)

## Visibility and safety of conclusions

For each transformed source point, require positive target Z, projection inside the target image, finite useful target depth, and agreement of expected versus observed target depth. Exclude depth boundaries and uncertain sampling; check both directions. The official flow implementation checks ray-distance consistency with absolute/relative margins and discusses nearest sampling around discontinuities; its thresholds are implementation policy, not universal ground truth. Use a frozen evaluator policy independent of both detectors.

`ArchVizTinyHouseDay` is a valid named environment and the examples use it, but inspected sources do **not** certify it as entirely static. Until dynamic content is audited, mark the initial static-scene assumption explicitly. Semantic class labels alone do not prove each surface is stationary. Sky/far-sentinel depths require masking. Camera pose and depth are simulator reference data and must remain evaluator-only; synthesized IMU may be a permitted detector stream.
