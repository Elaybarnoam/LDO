# Primary XYZ evaluation and secondary verifier audit

Completed: 2026-10-06. Sequence: MH_01_easy (development).

## What changed

Added `evaluation/compare.py audit --verification-report REPORT.json`. The loop task owns the audit in `evaluation/src/tasks/loop_closure/disagreement.py`; the existing singleton FIFO handler writes the dated final report. The audit reuses saved evidence and changes no model, XYZ formula, stereo policy or operational gate.

Primary evaluation includes all reported feature correspondences from both detectors. Secondary evaluation records the shared verifier's outcomes. Joining validates completed artifacts, saved file hashes, XYZ numerical/policy parity, timestamps, image identities and reported match counts. Missing or incompatible evidence fails explicitly. Tests cover retained rejected/untestable candidates, unknown evidence, duplicates, image/count mismatches and human report output.

## Primary results: all reported features

| Method | Supported | Contradicted | Untestable | XYZ coverage | Support among judgeable |
| --- | ---: | ---: | ---: | ---: | ---: |
| ORB + DBoW2 | 22,309 | 2,286 | 30,107 | 44.96% | 90.71% |
| LDO | 186,611 | 6,224 | 260,995 | 42.49% | 96.77% |

These are repeated feature observations from different candidate sets, not unique landmarks or correct loop counts. Unknown observations remain unknown. There are no missing operational records among the 1,540 ORB and 1,512 LDO externally evaluated pairs.

## Main finding

64 rejected LDO candidates have strong XYZ support; all 64 failed the operational 40% inlier-ratio gate. Of those, 61 estimated poses fall within the provisional reference tolerances (0.20 m and 5 degrees). ORB has 2 strongly supported rejected candidates, both rejected for fewer than 8 pose inliers; 1 estimate is within those pose tolerances.

Strong support is an explicitly recorded descriptive rule: at least 8 supported features, at least 80% support among judgeable features and at least 40% XYZ evaluation coverage. It changes no acceptance gate and is not independent loop truth. All pairs, including those below the highlight rule, remain in the report JSON.

Rejected LDO candidates collectively contain 16,451 XYZ-supported feature observations; rejected ORB candidates contain 282. These observations are retained in the primary evaluation rather than hidden by verification.

## Concrete example

LDO query `1403636676263555584`, history `1403636650763555584`:

- Reported assignments: 316.
- XYZ: 234 supported, 0 contradicted, 82 untestable.
- Reliable query-depth observations: 256.
- Verifier pose inliers: 102; ratio 39.84%, below the 40% gate.
- Pose translation error: 0.1278 m; rotation error: 1.2404 degrees.
- Median inlier reprojection error: 1.6397 pixels; 95th percentile: 2.8436 pixels.
- Decision: rejected for low inlier ratio.

Another LDO case (query `1403636681263555584`, history `1403636645763555584`) has 228 supported / 9 contradicted / 48 untestable observations, but 85/257 (33.07%) pose inliers. Its pose error is 0.0588 m and 0.2512 degrees. The disagreement is not limited to a single threshold-edge case.

## Interpretation and next step

XYZ evaluates reconstructed world-point agreement using reference poses and uncertainty. The operational verifier estimates one relative pose without those references and counts observations within a fixed 3-pixel reprojection threshold. The two tests have different residuals, uncertainty treatment and denominators; their percentages should not be equated.

The observed evidence identifies the 40% gate and its underlying fixed-pixel inlier definition as concrete development targets. It does not prove every rejected candidate is a correct loop. Do not automatically lower a threshold to make the examples pass. Next, inspect residuals against stereo uncertainty and calibrate a shared operational policy on labeled development pairs, preserving the external XYZ policy. Freeze that policy before held-out evaluation.

Independent loop annotation and held-out validation remain pending. No superiority claim is established by this audit.

## Validation

23 focused audit/comparison tests passed. Lint and formatting passed. External XYZ formula and config SHA256 hashes remain unchanged.
