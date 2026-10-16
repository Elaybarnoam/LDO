# Shared loop-verification implementation

Implemented in the authorized project `C:\Users\elayb\OneDrive\Documents\visual–IMU loop detector`.

## End-to-end topology

```text
ORB + DBoW2 / LDO saved chronological candidate traces
    → validated feature assignments and synchronized stereo observations
    → one shared operational PnP/RANSAC verifier
    → refinement + residual, inlier, cheirality and conditioning gates
    → accepted / rejected / insufficient evidence + metric relative pose
    → offline reference-pose assessment and independent loop-label metrics
    → child IPC publisher → parent singleton FIFO report writer
    → dated JSON + human-readable Markdown
```

The external XYZ task remains a separate evaluator of reported correspondences. Its numerical formulas and policy hashes are unchanged. Runtime verification never receives reference poses, loop labels or XYZ verdicts. Shared image-only stereo utilities preserve pinned worker bytes and reconstruction formulas.

## File ownership

- `loop_verification/`: immutable input contract, replaceable stereo preparation, PnP estimation/refinement, deterministic common acceptance and operational policies.
- `stereo_observations/`: reusable image-only disparity, calibration/rectification and stereo geometry.
- `evaluation/src/tasks/loop_closure/`: replay adapter, offline assessment policy, connection metrics, independent references/comparison workflow and supervised run configuration.
- `evaluation/src/tasks/feature_matching/`: unchanged external XYZ decisions and feature evidence viewer.
- `evaluation/src/benchmarks/loop_verification/`: shared benchmark subclass with inherited lifecycle and publisher.
- Existing orchestrator supervises the child; existing singleton handler owns final report writing.

## Commands

From the project root:

```powershell
uv run python evaluation/compare.py verify --supervised
uv run python evaluation/compare.py verify --query-limit 5
uv run python evaluation/compare.py verify --fixed-checks evaluation/output/fixed_matching_RUNID
uv run python evaluation/compare.py aggregate --reports REPORT1.json REPORT2.json
```

Windows forwards inference to the installed WSL environment. Separate `--verifier-config`, `--stereo-config` and `--assessment-config` policies are supported. Reports archive policy/source fingerprints and assignment-level evidence. Sequence aggregation rejects mixed experiment types and different policies and preserves unavailable metrics. Fixed-pair verification withholds detector recall.

## Real development result

Full supervised MH_01 replay: 3,052 candidate pair checks, 383 seconds. Evidence, IPC events and final report totals reconcile.

| Method | Pairs | Accepted | Rejected | Insufficient evidence |
| --- | ---: | ---: | ---: | ---: |
| ORB + DBoW2 | 1,540 | 454 | 56 | 1,030 |
| LDO | 1,512 | 1,071 | 394 | 47 |

Accepted pose estimates within provisional 0.20 m / 5 degree reference tolerances: ORB 423/454; LDO 929/1,071. All accepted pairs remain independently unlabeled, so these are pose diagnostics, not confirmed correct loops. Different candidate sets are evaluated with identical verification rules.

LDO provides more geometrically usable candidates and far fewer insufficient-depth cases here. It also has more rejections and more accepted estimates outside the provisional pose tolerances. Independent annotation, frozen operating points, held-out runs and training-overlap audit remain necessary to validate superiority.

The separate four-pair equal-cap smoke accepted 0 ORB pairs (4 insufficient) and 1 LDO pair (3 rejected). It validates wiring, not performance.

## Validation

Synthetic noisy/outlier projections verify metric pose direction, distortion and deterministic recovery. Tests cover unavailable depths, invalid inputs, degenerate geometry, runtime/reference separation, unknown-label handling, missed opportunities, sequence policy compatibility and unchanged external stereo formulas/worker bytes. The full regression suite passed: 111 tests, 1 skipped, and 19 subtests. Focused lint and formatting checks passed.

## Evidence locations

Original report: `evaluation/output/evaluation_2026-10-06_22-18-35_985980_cb90532a.{md,json}`.

Detailed assignment records, stereo evidence and immutable run source/policy snapshots: `evaluation/output/loop_verification_aa3cd64f8e0b4c3682ac54f2b8122b39/`.

Independent reference labels are still unknown; no labels were inferred from detector outputs or XYZ results. Current thresholds are provisional development defaults. The software workflow is implemented; the scientific claim is not yet validated.
