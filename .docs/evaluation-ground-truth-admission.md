# Mandatory ground-truth admission

Every detector candidate must pass the same admission gate before evaluation:

1. Both image timestamps lie inside the recorded reference-pose interval.
2. Both have a valid reference pose within the saved timestamp tolerance.
3. Reference pose and calibration files must be available and valid.

This is an invariant, not a configurable opt-out. No extrapolation or borrowing
poses from outside recorded coverage is allowed. The detector continues to run
without ground truth; admission is applied to its returned candidates before
independent feature matching, triangulation, classification, metrics or examples.

## Accounting

- `returned_pairs`: all detector candidates.
- `checked_pairs`: admitted and evaluated candidates.
- `excluded_pairs`: candidates rejected by the reference-pose prerequisite.
- `returned_pairs = checked_pairs + excluded_pairs` must always hold.

`candidate_excluded` IPC events and `excluded_pairs.jsonl` retain pair timestamps,
rank, role-specific missing-pose reasons and the admission tolerance. Exclusions
are absent from `pairs.jsonl`, outcomes, ranks, XYZ totals and example images.
The report handler verifies excluded event counts and complete accounting.
The human-readable report lists exclusions separately from evidence outcomes.

The OpenCV review tabs contain only admitted candidates. For older saved runs,
the reader filters records lacking available reference poses before grouping.
The header reports eligible and excluded counts. The raw retrieval trace remains
available for auditing and never becomes ground-truth-dependent detector input.

## Current MH_01_easy run

The previously returned 1,635 candidates contain 95 missing-reference pairs:
80 history frames before GT begins, and 15 current frames after GT ends.
They are excluded. The remaining review set contains 1,540 candidates:
489 XYZ-supported and 1,051 lacking XYZ support for other evidence reasons.
Ground-truth availability does not guarantee enough stereo depth or matches.
