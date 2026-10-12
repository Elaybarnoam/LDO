# Simulator-depth evaluator v2

This task rescores the saved individual feature correspondences from the frozen
two-environment TartanAir experiment. It does not run either detector, matcher or
operational verifier. Image-pair overlap labels and confirmed-event results retain
their original policy. EuRoC XYZ and reference_geometry remain unchanged.

From the project root in WSL:

```bash
PYTHONPATH=.:evaluation/src /opt/loop-detector/ldo-env/bin/python -m tasks.reference_depth_v2.workflow
```

`--config PATH` selects an explicit configuration. The default source is
`evaluation/output/unseen_tartanair/results.json`. Missing semantic archives are
downloaded at the pinned dataset revision and SHA256-checked; official label maps
use a pinned toolbox commit. Existing dataset installation manifests are preserved.

## Rules

Reference depth is axial Z, decoded losslessly from packed float32 PNGs. Existing
pinhole rays use array-index principal point (319.5, 319.5), corresponding to the
toolbox's half-pixel centers with optical center (320, 320).

- Finite positive depths on known non-sky surfaces have no metric distance cutoff.
- Sample inverse depth within the active bilinear footprint; zero-weight pixels
  do not affect the result. A planar surface has affine inverse depth in image
  coordinates. No interpolation occurs across a footprint exceeding 5% depth spread.
- Sky, unmapped semantics, invalid depth, outside-image points and mixed-depth
  footprints remain unknown. Integer feature locations sample their pixel center
  directly. This does not model additional uncertainty in feature localization.
- Keep symmetric reprojection <=3 px and XYZ error <=max(0.05 m, 0.005 times
  maximum endpoint Z). Larger metric tolerances do not override reprojection.

These are explicit geometric criteria, not calibrated correctness probabilities.
Simulator labels cannot remove ambiguity due to transparent or reflective surfaces.

## Output and verification

The existing FIFO evaluation handler writes dated Markdown/JSON reports in
`evaluation/output`. The latest report/summary pointer is
`evaluation/output/reference_depth_v2.json`. Raw compressed per-feature evidence,
sequence summaries, configuration and code snapshots are under
`/opt/loop-detector/experiments/reference_depth_v2/rescore_<id>/`.

Results include before/after counts, all verdict transitions, unknown reasons,
distance bins and scene-level totals. Input feature IDs/pixels are preserved;
original source reports, per-feature files, frame/depth images, semantic archives
and maps are checked or recorded with SHA256 hashes. Every sequence's old counts
must reconcile with the original report before publication.

Controlled tests cover near/far positives and negatives, camera translation,
wrong depth, inverse-depth interpolation, active-neighbour boundary handling,
sky, invalid pixels and actual saved-evidence replay with hash tampering.

See [the plan](../../../../.docs/reference-depth-v2-plan.md) and
[the completed results](../../../../.docs/reference-depth-v2-results.md).
