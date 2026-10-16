# Connection diagnostics implementation plan

Date: 2026-10-09.

## Measurement layers

1. Preserve the frozen per-feature XYZ evaluator and its supported / contradicted / untestable observations. Add an optional statistical interface accepting full joint world-point covariance, including cross-correlation, without changing existing verdicts. Missing or uncalibrated uncertainty cannot produce a statistical correctness verdict.
2. Preserve the current relative-pose convention (historical camera from query camera), translation norm and geodesic SO(3) angle. Add validated SE(3) residual and optional calibrated covariance consistency assessment. Continuous translation/rotation distributions, empirical CDFs and tolerance sensitivity accompany threshold counts.
3. Reuse independently reviewed scene/event metrics, development-only threshold selection and frozen held-out controls. Unknown scene labels stay unknown; pose results do not replace them.

## Diagnostic workflow

A new `diagnose` command consumes a completed, hash-validated full verifier/XYZ audit. Join every candidate by method, timestamps and image identities. Reconcile accepted counts, inspect all accepted failures, retain individual verifier diagnostics, and describe XYZ evidence without assigning causal certainty. Export dated Markdown/JSON through the existing FIFO writer, plus a complete candidate CSV and accepted-failure JSONL.

For each method, report accepted pose distributions and empirical CDFs, error-type counts (translation only / rotation only / both), and failure evidence groups. Strong support and contradiction are descriptive policies, not new acceptance gates. Provide development quality/risk sweeps using observable verifier diagnostics; never filter on ground truth at runtime. These are exploratory curves, not held-out claims or production threshold changes.

## Numerical contracts

Statistical distance is r.T @ solve(C, r); reject malformed, asymmetric, singular or non-positive covariance. XYZ uses r = p_world_query - p_world_history and C = Cq + Ch - Cqh - Chq. Pose uses Log(inv(T_reference) @ T_estimated), with residual order translation tangent then rotation vector in radians. Covariance must be expressed in that same tangent, include joint/reference uncertainty, and be explicitly calibrated. Chi-squared coverage is conditional on the Gaussian approximation and calibration; agreement is evidence, not identity proof.

## Verification and results

Test analytic geometry, coordinate direction, correlated covariance, unknown/uncalibrated handling, threshold boundaries, aggregation, risk ties, evidence joins and report output. Run the new command on all saved MH_01 candidates. Record actual diagnostics and existing independent-label limitations. No model, XYZ threshold or verifier gate changes.


## Implemented

- New `connection_diagnostics.py` and `statistical_geometry.py` offline modules.
- New `evaluation/compare.py diagnose` command and Markdown renderer integration with the existing FIFO writer.
- Recomputed reference-relative pose errors and SE(3) logarithmic residuals, empirical CDFs, tolerance sensitivity and full candidate/failure exports.
- Streamed original feature assignments to identify precisely the PnP inliers and retain their XYZ verdict counts and unknown reasons, validating source hashes, assignment identity and image hashes.
- Optional calibrated statistical geometry interfaces; absent uncertainty remains explicitly unavailable.
- Existing independent review/event measurement and frozen development/held-out controls retained.
- Development-only quality/risk sweeps; no model or verifier acceptance gates changed.
- Full suite: 160 passed, 1 skipped, 19 subtests passed. Lint and formatting checks passed. Frozen XYZ code and policy SHA256 values are unchanged.

Command guide and mathematical contracts: `evaluation/src/tasks/loop_closure/CONNECTION_DIAGNOSTICS.md`.
