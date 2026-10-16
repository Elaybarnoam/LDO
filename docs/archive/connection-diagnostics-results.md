# Connection diagnostics: results

Date: 2026-10-09. Data: MH_01_easy development sequence. No detector, verifier acceptance gate or frozen XYZ formula/threshold was changed.

## Implemented measurements

- Independent per-feature XYZ evidence, separately for all matches and the exact assignment IDs PnP retained as inliers.
- Recomputed ground-truth relative-pose errors for saved estimates, with continuous distributions, empirical CDFs, tolerance sensitivity and SE(3) logarithmic residuals.
- Optional calibrated covariance consistency interfaces for world points and relative poses, preserving cross-correlation through joint covariance. Missing or uncalibrated uncertainty produces no statistical verdict.
- Development quality/error-rate curves using observable verifier diagnostics; existing independent scene/event metrics and frozen held-out controls remain available.
- Dated Markdown/JSON reporting, all-candidate CSV and individual accepted-failure JSONL, validated against original evidence hashes and image/feature identities.

## Accepted-pose results

All 3,052 candidate records were reconciled. The current application tolerance is translation error <= 0.20 m AND rotation error <= 5 degrees.

| Measurement | ORB + DBoW2 | LDO |
| --- | ---: | ---: |
| Accepted connections | 454 | 1,071 |
| GT-inconsistent accepted estimates | 31 (6.83%) | 142 (13.26%) |
| Translation-only failures | 15 | 83 |
| Translation and rotation failures | 16 | 59 |
| Rotation-only failures | 0 | 0 |
| Median translation error | 0.0268 m | 0.0329 m |
| P95 translation error | 0.2597 m | 0.7124 m |
| Median rotation error | 1.0469 degrees | 1.0364 degrees |
| P95 rotation error | 3.9462 degrees | 5.4897 degrees |

Every failed accepted pose exceeded translation tolerance. LDO has a substantially larger translation-error tail despite a similar median error. This does not identify whether the scene association is false.

## Exact PnP-inlier XYZ evidence inside the failed accepted poses

| Verdict | ORB | LDO |
| --- | ---: | ---: |
| Supported feature observations | 365 | 493 |
| Contradicted feature observations | 4 | 27 |
| Untestable feature observations | 34 | 3,644 |
| Judgeable fraction | 91.56% | 12.49% |

All these untestable inliers carry the saved reason `reliable_stereo_depth_unavailable`. This check needs reliable depth in both observations; operational PnP uses query depth plus historical 2D pixels. A PnP inlier can therefore exist without enough independent stereo evidence to judge its correspondence.

Using the documented descriptive evidence policy on the exact PnP subset:

- ORB failures: 28 have dominant XYZ support; 3 have mixed/insufficient evidence.
- LDO failures: 22 have dominant XYZ support; 1 has dominant contradiction; 119 have mixed/insufficient evidence.

These are investigation categories, not proven causes or scene labels. XYZ support uses the preserved assumed-noise policy and does not guarantee sub-20-cm pose accuracy. Repeated feature observations are not independent landmarks. One contradiction-dominant pair does not mean there is only one false revisit.

## Exploratory development quality curve

At an error-rate ceiling equal to the ORB baseline (6.83%), the saved LDO pose-condition curve contains a point retaining 946 accepted connections: 884 within pose tolerance and 62 outside (6.55%). This point was selected after looking at development outcomes. It is not an independently validated improvement, a calibrated uncertainty threshold, or a changed production gate. It identifies a quality rule worth freezing and testing on held-out sequences.

## Measurements that remain unavailable

Actual scene false positives and overall distinct-revisit recall require independent scene labels; none were fabricated. Statistical pose compatibility requires calibrated residual covariance, which the saved runs do not contain. The new interfaces support that input but do not invent it.

## Verification

160 tests passed, 1 skipped, 19 subtests passed. Lint and formatting checks passed. Tests include SE(3) log/exponential agreement near zero and pi, coordinate conventions, correlated covariance, missing/uncalibrated uncertainty, exact PnP feature joins and changed-evidence rejection. The frozen XYZ implementation and policy SHA256 values remain unchanged.

Run guide: `evaluation/src/tasks/loop_closure/CONNECTION_DIAGNOSTICS.md`.
