# Frozen LDO evaluation on two new TartanAir environments

## Selection, before downloads and model outcomes

Test AbandonedFactory2 (indoor infrastructure) and DesertGasStation (outdoor,
lighting variation). Both differ from TinyHouse, RetroOffice and CountryHouse.
They were chosen from official scene descriptions and archive sizes, not model
performance. All Data_easy trajectories present in each pinned archive are used;
trajectory IDs are discovered from the installation before inference.

[Official environment descriptions](https://tartanair.org/environments.html).
Repository: `theairlabcmu/tartanair2`, revision
`0d2d145e973832742a2aaa04b7d2ebffc8d82817`.
Download stereo front images, left reference depth and IMU/pose archives with
upstream SHA256 verification. Total compressed size: 8,127,604,149 bytes.

Unseen means unused in our own adaptation/development. Upstream pretrained
exposure and shared synthetic assets are unaudited; this is not a strict OOD claim.

## Frozen detector and evaluator

Installation metadata confirms AbandonedFactory2 P000–P005 (793 sampled frames)
and DesertGasStation P000–P004 (693 sampled frames): 11 trajectories and 1,486
sampled frames total. This selection was recorded before either detector ran.

- ORB + DBoW2: existing pinned, upstream-parity-verified native implementation.
- LDO: `ldo/configs/optimized-confidence.yaml`, pretrained MegaLoc + SuperPoint +
  LightGlue, confidence 0.3, adaptive inference, no candidate policy or adapted head.
- Both receive the same grayscale cam0 images, approximately 2 Hz, K=5 and
  5-second temporal exclusion, with reset between trajectories. Neither uses IMU
  or reference data during inference.
- The existing independent reference-geometry implementation and numerical gates
  are frozen. Reference depth/pose assesses every reported feature match and all
  eligible image-pair visibility labels. No stereo estimator, RANSAC, PnP or
  operational verifier is used. Original EuRoC XYZ code/config remain unchanged.
- Retain the 50 m depth limit and depth-boundary uncertainty handling outdoors.
  Low coverage must be reported, not repaired by test-driven gate changes.
- No training, threshold selection or checkpoint selection on these environments.

## Execution and output

1. Persist config/source/native-build hashes before inference.
2. Download, hash-check and extract both environments into separate WSL roots.
3. Freeze all source trajectory IDs, export replay images and construct independent
   reference labels before running either model in each environment.
4. Run the frozen ORB and confidence-only LDO detectors, retaining their original
   feature assignments and raw candidate traces.
5. Independently score every assignment. Publish per-environment and per-trajectory
   counts plus combined totals through the evaluation file handler.

Bulk datasets and raw experiment artifacts stay under `/opt/loop-detector/` to
avoid repeated OneDrive filesystem overhead. Configurations, progress manifests,
dated human-readable reports and JSON summaries are available in the project.
The runner can resume from completed, hash-checked stages without mixing runs.

## Metrics and interpretation

Report correct/incorrect/unknown feature matches, judged precision, judgeable
coverage and accuracy bounds including unknowns. Separately report candidate
TP/FP/unknown, precision bounds and confirmed event hits. Events are not weighted
by how many redundant pairs reached them. Report each environment and trajectory,
not only pooled numbers. Overall recall remains withheld when labels are
incomplete. A false candidate means below the frozen 20% bidirectional visible
overlap rule, not necessarily a different semantic room or an inaccurate pose.

Smaller raw false-feature counts alone are not evidence of superiority when the
models report different numbers of correspondences. General conclusions require
consistent behavior across environments and later real-world testing. No latency
or downstream SLAM accuracy claim is made by this experiment.
