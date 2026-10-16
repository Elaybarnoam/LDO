# Datasets for measuring LDO feature and revisit correctness

Research date: 2026-10-09. Recommendation based on primary dataset documentation, not downloaded sequence inspection.

## Decision

Use a controlled geometry benchmark followed by a real-world external-map benchmark. Keep EuRoC as continuity evidence. This targets our current limitation: external XYZ cannot judge many feature observations because stereo depth is unavailable. Choosing another pose-only dataset would not directly solve that limitation.

## 1. TartanAir V2: first choice for controlled geometry

The official release provides synchronized stereo RGB, aligned float32 simulator depth, camera poses, and pose-derived simulated IMU. Its flow tools expose field-of-view and covisibility masks. This makes it a strong candidate for checking arbitrary temporal feature pairs without estimating reference depth from their appearances. Static scenes, valid depth and occlusion masks must be selected explicitly. The simulator does not establish real-world generalization. Sources: [modalities](https://tartanair.org/modalities.html), [official toolkit](https://github.com/castacks/tartanairpy).

Proposed use (our design): back-project each reported feature using reference depth, transform with reference camera poses, compare world points, and check projected visibility against the other depth image. Independently sample the eligible image-pair universe to establish scene-overlap opportunities, including pairs missed by both models. Freeze physical overlap thresholds and continuous-event grouping. Confirm depth convention, camera axes and timestamp mapping with synthetic projection tests before evaluating.

## 2. Oxford Spires: first choice for real-world map-backed evaluation

The sensor rig includes three color cameras and camera-synchronized IMU. A separately surveyed terrestrial laser-scanner map is available. The reference trajectory comes from registering mobile LiDAR to that map; the map's millimetric measurements do not mean the camera trajectory is millimetric. Official documentation places trajectory accuracy at roughly 1?2 cm and limits trajectory ground truth to core sequences within map coverage. Sources: [dataset](https://ori-drs.github.io/datasets/oxford-spires/), [ground-truth details](https://github.com/ori-drs/oxford_spires_dataset/wiki/Ground-Truth).

Proposed use: select a core sequence with revisits, render reference camera depth from the surveyed map using GT poses, and keep registration, sampling, visibility and dynamic-object uncertainties explicit. This is an external geometric reference for evaluating camera/IMU detectors; it does not require giving LiDAR to either detector. Fisheye projection and map coverage require a new dataset adapter.

Important implementation distinction: the repository's current depth-generation example consumes `processed/vilens-slam/undist-clouds`. That output is not automatically surveyed-map ground truth. Use the independent TLS reference map and its provenance for our evaluator. Source: [official repository depth-generation example](https://github.com/ori-drs/oxford_spires_dataset#depth-image-generation).

## 3. ETH V4RL Dense Reconstruction: small real-world validation

Two scenes (desk and pipe) provide stereo, IMU, ToF/RGB-D, Vicon sensor poses, a Leica-scanned scene and relevant calibration. This is unusually suitable for checking whether our geometry evaluator itself is correct. Its limited scene diversity makes it a diagnostic benchmark, not enough evidence for broad loop-detection superiority. Source: [ETH dataset documentation](https://asl.ethz.ch/v4rl/research/datasets-code/V4RL-Dense-Reconstruction-Dataset.html).

## 4. OpenLORIS-Scene: practical RGB-D and repeat-traversal option

Provides RGB-D and IMU from a D435i, stereo fisheye and IMU from a T265, and repeated trajectories with environmental changes. Office trajectories use motion capture; other scenes use offline LiDAR-based trajectories. Aligned RGB-D could improve evaluation coverage, but sensor depth is noisy and is not perfect per-pixel ground truth. Match IMU to the image device, respect synchronization, and do not assume D435i depth is directly aligned to T265 pixels. Source: [official dataset](https://lifelong-robotic-vision.github.io/dataset/scene.html).

## What changes in our experiment

- Both models receive identical allowed visual/IMU inputs; external depth/maps remain evaluator-only.
- Preserve the current frozen EuRoC XYZ experiment. Add a versioned reference-depth provider to the external evaluation approach and run both methods under the same new policy.
- Do not put reference depth into the operational verifier when claiming unchanged deployed behavior. An oracle-depth verifier would be a separate ablation.
- Reference geometry can support independently derived overlap labels, but each dataset is not automatically a ready-made, exhaustively annotated loop-event benchmark. Freeze visibility, sufficient-overlap, static-region, uncertainty and event-boundary rules. Retain unknown where reference evidence is absent or ambiguous.
- Retain all eligible opportunities, including those missed by both detectors. Report pair precision, event recall at a shared development-selected precision, pose-error distributions and unknown coverage separately.
- Split by environment/site rather than adjacent frames; audit pretrained model training overlap. A different dataset is not automatically out of distribution or held out.

Recommended order: TartanAir V2 controlled subset, small ETH geometry sanity check if downloadable, then one Oxford Spires core sequence before expanding sites. Dataset-specific download availability and coverage must be checked at installation time. No datasets were installed during this research.
