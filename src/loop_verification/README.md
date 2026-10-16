# Shared operational loop verification

This package estimates a metric relative camera pose from reported temporal feature assignments and query stereo depth. Both ORB and LDO use the same implementation and policy. It is reusable without the evaluation program.

## Input → output

```text
Query raw stereo images + calibration
    → image-only disparity and reliable query-camera XYZ
Reported query/history feature assignments + historical raw pixels
    → PnP/RANSAC → inlier refinement → residual recomputation
    → count / ratio / residual / cheirality / conditioning gates
    → accepted | rejected | insufficient_evidence
      + T_HQ + inlier feature IDs + diagnostics
```

`T_HQ` maps query camera points into the historical camera: `P_H = R_HQ P_Q + t_HQ`. Translation is in metres. Calibration and pixels must refer to the same raw camera; OpenCV receives its distortion coefficients.

`VerificationInput` validates chronology, one-to-one assignment IDs, observation shapes, raw-image bounds and finite positive usable depths. Invalid input raises an error. Missing or unreliable depth remains unusable; the pipeline does not create depth by triangulating the alleged temporal correspondence.

## Components

- `stereo_depth.py`: synchronized image-only stereo preparation and bounded per-frame point-depth caching.
- `contracts.py`: typed observation/result interfaces.
- `pose_estimation.py`: seeded EPnP RANSAC, LM refinement, recomputed inliers and conditioning diagnostics.
- `acceptance.py`: shared deterministic operational gates.
- `verifier.py`: observation-only pipeline.
- `config.yaml`: provisional operational thresholds.
- `stereo.yaml`: stereo model/runtime configuration and observation reliability gates.

The shared disparity implementation is in `stereo_observations/`. Model predictions are cached using images, calibration, model and policy fingerprints. Historical cache reuse is explicitly validated by the evaluation adapter. Pinned worker bytes are retained because their hash is part of model/runtime cache provenance.

Reference poses, loop labels and external XYZ verdicts are absent from the runtime API. `src/loop_eval/tasks/loop_closure/verification.py` validates replay data, invokes this package, then assesses its output offline using `pose_assessment.py` and the separate `assessment.yaml`.

## Running and interpreting

```powershell
uv run python evaluation/compare.py verify --supervised
uv run python evaluation/compare.py verify --query-limit 5
uv run python evaluation/compare.py verify --fixed-checks evaluation/output/fixed_matching_RUNID
```

Windows inference forwards to the installed WSL environment. The supervised path uses the existing orchestrator, child publisher and singleton FIFO report handler. Only that handler writes the dated final report; detailed evidence and source snapshots are saved in the artifact directory cited by it.

Acceptance means the observations satisfy the configured geometric policy. It is not itself independent proof of a correct loop. Rejection is not automatically a false positive. Insufficient evidence does not imply an incorrect match. Unknown reference labels withhold accuracy claims even when estimated poses have small reference errors.

The current numerical gates are development defaults, not publication-calibrated operating points. Independent annotation and frozen held-out experiments remain necessary before claiming superiority. Fixed-pair verification isolates matching/geometry and does not measure detector recall.
