# Reference-depth evaluator v2

This is an evaluator revision after inspecting held-out results, not a new unseen
model experiment. Keep all detector outputs and the old results unchanged.

## Scope and rules

- Replay all saved individual ORB and LDO feature correspondences in the two new
  TartanAir environments. Preserve image-pair labels and confirmed-event counts;
  changing pair overlap is a separate experiment.
- Accept any finite positive depth on a known non-sky semantic surface. No metric
  near/far cutoff. Download the official left semantic masks at the same pinned
  dataset revision; use the upstream semantic mapping at a pinned toolbox commit.
- At fractional feature coordinates, inspect only the one to four pixels having
  nonzero bilinear weights. Require valid depth and known non-sky semantics in
  that footprint. Keep mixed-depth footprints unknown when the existing 5%
  spread gate fails. Interpolate inverse axial depth on smooth surfaces (exact
  for a plane under the pinhole model). Never interpolate across discontinuities.
- Keep the original camera convention and XYZ/reprojection tolerances:
  max(0.05 m, 0.005 times endpoint depth), and 3 px symmetric reprojection.
  The XYZ threshold already scales with depth. This is an operational tolerance,
  not a calibrated probability or proof of subpixel localization accuracy.
- Sky and unmapped semantic values remain unknown. A finite renderer depth is
  insufficient by itself to establish a physical surface.
- Record old-to-new feature verdict transitions and explicit abstention reasons.
  Include distance bins so an apparent gain from distant/background matches is
  visible. Publish per-scene and combined metrics through the shared writer.

## Validation and provenance

Use controlled positive and negative correspondences at near and far depths,
nonidentity camera poses, planar subpixel interpolation, inconsistent depth,
sky, invalid pixels and mixed-depth boundaries. Validate that long distance does
not make displaced image matches pass. Verify source report, per-feature evidence,
frame/depth hashes and semantic assets; record config/source hashes in the new
dated report. Do not rerun feature detection or matching.

## Source checks

[TartanAir modalities](https://tartanair.org/modalities.html) documents lossless
float32 depth, aligned images and large finite sky values. The official
[reader](https://github.com/castacks/tartanairpy/blob/158a6844d782942110967325ca3082f50ab2bfc7/tartanair/reader.py)
distinguishes axial depth from ray distance and uses half-pixel ray centers:
array-index principal point 319.5 matches the existing convention. The official
[semantic mappings](https://github.com/castacks/tartanairpy/blob/158a6844d782942110967325ca3082f50ab2bfc7/segfiles.zip)
identify sky independently of detector output.

More judged features can become incorrect as well as correct. Coverage improvement
alone does not establish reliable or superior detector predictions. Original
EuRoC XYZ and frozen TartanAir reference code/config remain unchanged.
