# Dataset references for independent loop-detector evaluation

Research date: 2026-10-09. Scope: camera-based detector inputs; IMU where available; depth, meshes and LiDAR may be evaluator-only references. No datasets installed and no evaluation code changed.

## Recommendation

Use two complementary additions: **TartanAir V2 for controlled correspondence correctness**, and **Oxford Spires for real camera/IMU sequences with survey geometry**. Use ETH V4RL for small controlled real-geometry checks; ScanNet++ is an additional real-scene matching option. Keep EuRoC for compatibility with the existing stereo/IMU pipeline. Hilti-Oxford offers challenging real VI sequences, but its advertised millimetre truth must not be mistaken for dense six-degree-of-freedom camera truth.

## TartanAir V2: best controlled geometry test

Official modality documentation supplies synchronized stereo imagery, aligned float32 depth and camera poses. Stereo baseline is 0.25 m; standard images are 640×640 at 10 Hz. Optical flow is derived from pose/depth, with forward/backward field-of-view and covisibility masks; the toolkit supports regeneration rather than assuming every flow file is precomputed. IMU is synthesized by differentiating interpolated poses, with configurable noise. These are simulator references, not independent physical measurements. [Official modalities](https://tartanair.org/modalities.html)

The downloader explicitly accepts image/depth/IMU modalities and camera selection, allowing a small stereo subset rather than the entire collection. [Official examples](https://tartanair.org/examples.html)

**Proposed evaluation:** the evaluator uses simulator depth and pose to project a reported query feature into the historical image. Require valid depth, visibility and consistent target depth before scoring correspondence error. Aggregate independently established visible shared surfaces into pair overlap; apply frozen overlap thresholds and temporal exclusion to define revisit events. This is our proposed protocol, not supplied loop-event labels. Static-scene geometry should be the initial scope; dynamic objects need separate treatment. Select trajectories after auditing actual revisit overlap rather than assuming all trajectories contain useful loops.

**Boundary:** use depth only in the evaluator; do not silently replace the frozen EuRoC XYZ stereo evaluator. Add a separately named/versioned reference-geometry evaluation. Simulation can isolate mistakes and reduce stereo-induced unknowns, but cannot establish real-world superiority alone.

## TartanAir V1: version distinction

The original project describes synthetic stereo, depth, poses, flow and simulated IMU generation. However, the published V1 tools' documented downloadable tree includes image/depth/flow/segmentation/pose and does not expose an IMU download option. Therefore prefer V2 when packaged IMU availability matters; do not promise every V1 archive contains IMU. [Original project](https://theairlab.org/tartanair-dataset/), [V1 tools](https://github.com/castacks/tartanair_tools)

## ScanNet++: strong real-scene geometry reference

The dataset couples survey laser geometry with DSLR images and iPhone RGB-D video. Current documentation supplies aligned scan meshes, metric scan-aligned COLMAP poses, tools to render mesh depth, anonymization masks and iPhone depth. It also explicitly lists `pose_intrinsic_imu.json` with ARKit poses and IMU information. Thus describing ScanNet++ categorically as having no IMU would be incorrect. iPhone depth is lower-resolution measured LiDAR depth; mesh-rendered depth is processed reference geometry, and ARKit/COLMAP poses are estimates rather than exact independent motion-capture truth. [Official documentation](https://scannetpp.mlsg.cit.tum.de/scannetpp/documentation)

**Fit:** promising for measuring correspondence correctness and physical scene overlap using independent laser geometry. It is not a drop-in replacement for synchronized stereo EuRoC: evaluate RGB matching first; verify IMU timing, calibration and completeness before claiming VI compatibility. Exclude mesh holes, anonymized pixels, depth discontinuities, dynamic objects and uncertain registration. Use splits with released geometry; NVS test geometry is withheld. Access requires registration/application. [Dataset access](https://scannetpp.mlsg.cit.tum.de/scannetpp/)

## Oxford Spires: preferred larger real VI and scene-geometry addition

Three global-shutter colour cameras operate at 20 Hz with camera-synchronized 400 Hz IMU. A separate terrestrial laser survey supplies a millimetre-accurate map; core-sequence reference trajectories are centimetre-accurate estimates obtained by registering onboard LiDAR to that map. Calibration is released. Millimetre map accuracy does not imply millimetre trajectory accuracy. Only core sequences carry the stated trajectory reference. [Official dataset](https://ori-drs.github.io/datasets/oxford-spires/)

**Important implementation distinction:** the current README's depth-generation example projects processed `vilens-slam/undist-clouds`, not the independent TLS map. That output must not be mislabeled independent survey depth. For our evaluator, explicitly select and record survey geometry, reference trajectory, calibration and visibility rendering; audit what each tool actually consumes. [Official repository](https://github.com/ori-drs/oxford_spires_dataset)

**Fit:** real camera/IMU inputs plus separately acquired static geometry offer a strong route beyond EuRoC's stereo-depth coverage limit. Detector inputs remain images/IMU only. Fisheye/multi-camera adaptation and occlusion/registration masks are required. No supplied loop-event annotation matching our definition was established here.

## ETH V4RL Dense Reconstruction: small real evaluator validation

Two scenes, a desk and a pipe structure, provide monochrome stereo, MEMS IMU, ToF depth and RealSense RGB-D. External Vicon supplies 6DoF sensor poses; Leica MS50 scans supply scene geometry, with ICP alignment. Intrinsics and camera/IMU/depth/Vicon extrinsics are released. [Official ETH dataset](https://asl.ethz.ch/v4rl/research/datasets-code/V4RL-Dense-Reconstruction-Dataset.html)

**Fit:** excellent small controlled checks of coordinate conventions, stereo depth and uncertainty-aware XYZ decisions against independent physical references. Two local scenes cannot establish large-scale loop-detection generalization or long-term revisits. Keep measured depth and scan geometry evaluator-only.

## Hilti-Oxford 2022: real VI stress test, with ground-truth caveats

Five camera streams and an IMU are calibrated and synchronized; LiDAR need never enter either detector. Challenge truth consists of sparse surveyed **positions**, not dense 6DoF camera poses. Current downloads offer dense 6DoF truth for Exp14, Exp16 and Exp18; Exp23 repeatedly revisits the ground hall but is currently listed with sparse 3DoF truth only. Survey laser clouds are also released. [Official downloads and formats](https://hilti-challenge.com/dataset-2022)

The paper explains that dense poses are generated through LiDAR-inertial registration to the survey map, with approximately 1–2 cm accuracy. Millimetre accuracy applies to sparse surveyed controls; it must not be assigned to every dense pose. [Dataset paper](https://robots.ox.ac.uk/~mfallon/publications/2023RAL_zhang.pdf)

**Fit:** useful real camera/IMU stress cases after an adapter and calibration checks. Before dense correspondence evaluation, check available pose coverage and independently establish view visibility; sparse position control points alone cannot judge arbitrary temporal feature matches.

## ScanNet: useful secondary RGB-D matching benchmark

Original ScanNet provides RGB-D sequences, estimated camera poses and reconstructed surfaces. These support depth/pose-based correspondence checks, but geometry and poses come from RGB-D reconstruction rather than an independent survey. Treat it as a secondary matching benchmark, not the first choice for a strict stereo/IMU mission. [Official ScanNet](https://www.scan-net.org/ScanNet/)

## What none of these guarantees

The reviewed releases do not establish a ready-to-use detector-independent loop-event annotation set matching our definition. Dense reference geometry enables a reproducible visibility/overlap protocol; it does not eliminate choices about minimum overlap, temporal separation, event boundaries or uncertainty. Document these choices before scoring either model. Also audit pretrained-component training datasets before describing a held-out dataset as genuinely out of distribution.

## Practical next experiment

1. Download only a few TartanAir V2 stereo trajectories and evaluator-only depth/poses; inspect revisit opportunities first.
2. Freeze a visibility-aware reference correspondence/overlap policy without detector outputs.
3. Run both frozen detectors with equal history and candidate budgets; report false correspondences, pose error, reference coverage, pair precision and distinct-event recall separately.
4. Validate geometry calculations on ETH V4RL, then the claimed effect on Oxford Spires core sequences. ScanNet++ supplies an additional geometry-available real-scene matching test. Keep all reference sensor data isolated from detector inputs.
5. Use one common, versioned external reference-provider interface for both methods. Freeze masking, uncertainty and overlap rules independently of the detector; never compare one method using stereo-estimated truth against the other using survey truth.
