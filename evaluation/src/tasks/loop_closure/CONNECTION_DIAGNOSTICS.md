# Connection mathematics and diagnosis

## Run

From the project root (Windows forwards analysis to the installed WSL environment):

```powershell
uv run python evaluation/compare.py diagnose --verification-report evaluation/output/comparison_2026-10-06_23-18-20_943354_ad54ab7e.json
```

The source must be a completed full-run `audit` report containing both operational records and external XYZ evidence. The command validates original operational/XYZ hashes, image identities, assignment counts and reference/calibration files. It recomputes each available pose error from the saved estimated transform and reference camera poses. The numerical XYZ evaluator is not rerun or modified.

Outputs are a dated Markdown/JSON report via the existing FIFO writer, complete candidate CSV, and JSONL containing every accepted pose failure. Individual failure entries retain PnP diagnostics, exact PnP inlier XYZ counts, unknown reasons, all-match XYZ evidence and SE(3) residuals. Artifact hashes are saved in the report. All original XYZ records are streamed once; no inference runs.

## Three separate questions

1. **Feature association:** do the two stereo reconstructions agree in world coordinates? The frozen XYZ evaluator answers supported / contradicted / untestable under its existing assumed-noise policy. We report both all reported matches and the precise PnP inlier assignment subset. Counts are repeated observations, not necessarily independent landmarks.
2. **Connection pose:** how inaccurate is the estimated historical-from-query transform? Translation norm and SO(3) geodesic rotation error are reported continuously with empirical CDFs, median, P90/P95 and maximum. Tolerance sensitivity is a separate application-policy diagnostic. A pose failure is not itself a scene false positive.
3. **Actual revisit:** do the images share identifiable static physical scene, and how many continuous revisit events are detected? This uses the independent scene reference in `revisits/`; pose proximity or XYZ aggregates never silently supply scene labels.

## Optional statistical interfaces

`statistical_geometry.world_point_consistency(query_world, historical_world, joint_covariance, calibrated=...)` accepts a 6x6 joint covariance ordered [query XYZ, historical XYZ] in world coordinates. The caller must propagate stereo, poses, calibration and cross-correlation into this covariance. The difference covariance is Cq + Ch - Cqh - Chq, rather than blindly summing two independent estimates.

`statistical_geometry.pose_consistency(estimate, reference, residual_covariance, calibrated=...)` uses Log(inverse(reference) @ estimate), ordered [rho in metres, phi in radians]. The covariance must describe that residual in the same reference tangent; a Rodrigues/translation covariance cannot be passed without conversion and inclusion of reference uncertainty. The logarithm uses the inverse SO(3) left Jacobian for rho. `assess_pose` also accepts this optional residual covariance without changing its existing default output.

Both interfaces compute Mahalanobis squared distance using a linear solve. Covariances are checked for finite values, symmetry and definiteness. Missing covariance returns unavailable; assumed/uncalibrated covariance can supply a numerical distance but never a compatibility verdict or p-value. Calibrated covariance enables a conditional chi-squared test (3 or 6 degrees of freedom). Gaussian approximation, covariance calibration and static-scene assumptions remain essential; compatibility is not proof of identity.

Saved runs do not contain calibrated joint pose uncertainty. Their statistical pose verdict is explicitly unavailable; no covariance is inferred from a condition number or fitted residuals alone.

## Diagnosis interpretation

A failure with dominant XYZ support suggests investigating pose fitting, depth sensitivity, geometry conditioning and frame conventions. Dominant contradiction suggests incorrect associations. Mixed or insufficient evidence cannot establish either cause. The descriptive evidence policy requires at least 8 judgeable matches, 40% judgeable coverage, and 80% agreement or contradiction; it changes no acceptance gate. Exact PnP-inlier evidence is reported separately from all-match evidence because these can disagree.

Development quality/risk sweeps retain tied quality scores together and use observable inlier ratio, median reprojection error or pose condition. Ground truth judges outcomes only offline. The post-hoc matched-risk diagnostic uses the ORB baseline pose-error rate; it is exploratory, not an independently validated operating point. Held-out sequences do not receive development sweeps. Choose and freeze a quality policy on development data before applying it to a separately evaluated sequence. The pose condition number is a heuristic, not calibrated uncertainty.

## Independent event measurement

See `revisits/README.md` for detector-blind review, two-reviewer consensus, immutable snapshots, event grouping, candidate budgets, development-only precision calibration, frozen held-out settings and temporal/event-block uncertainty. No independent scene decisions currently exist for the saved MH_01 snapshot, so actual scene false positives, overall event recall and target-precision selection remain unavailable.
