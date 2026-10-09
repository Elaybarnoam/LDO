# Plan: feature correspondence evaluation

Updated: 2026-10-06. Status: implemented; maintain as the external evidence task.

## Question

For the feature correspondences reported by ORB or LDO, how many can be judged independently, and how many agree or disagree in reference-world XYZ?

## Topology

```text
Saved ORB/LDO feature coordinates and assignments
    + synchronized stereo images and calibration
    + reference camera poses (evaluation only)
        → existing stereo preparation and uncertainty gates
        → unchanged per-correspondence XYZ calculation
        → supported / contradicted / untestable evidence
        → shared FIFO report writer and per-feature viewer
```

## Ownership

- `xyz/`: input adapters, stereo preparation, numerical checks, evidence and coverage diagnostics.
- `xyz/config.yaml`: existing frozen numerical thresholds.
- `viewer/`: feature navigation, verdict overlays and technical explanations.
- Shared infrastructure owns benchmark supervision, event publishing and final reports.

## Maintenance rules

Preserve reported pixel coordinates, assignment IDs and provenance. Admit evaluation pairs only when both reference poses are valid. Missing depth or unreliable geometry produces untestable evidence, not a false-positive label. Preserve numerical XYZ formulas and thresholds during loop-verifier development. Report micro totals and per-pair aggregates; repeated feature observations are not unique landmarks or loop counts.

The loop task may read these outputs for comparison. Operational loop verification must not consume this task's ground-truth poses or XYZ verdicts.

## Validation

Retain existing numerical hash/AST regression checks, evidence integrity tests, stereo-cache validation, missing-pose admission checks, coverage reconciliation and viewer tests. Existing tests passed after task separation. No detector retraining or numerical policy change is part of this organizational plan.

## Remaining work

No new feature-evaluation algorithm is required for the shared-loop-verifier milestone. Any later evaluator changes require a separate versioned protocol and equal re-evaluation of both methods.
