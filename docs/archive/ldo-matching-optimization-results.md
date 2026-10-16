# LDO matching optimization: results

Completed 2026-10-10. All agreed pretrained matching ablations and the fresh environment test ran. No fine-tuning was performed.

## Conclusion

The development-selected configuration raises LightGlue confidence from **0.3 to 0.4**, retaining SuperPoint, 1,024 points, native resolution and adaptive inference. On fresh OldTownFall data it removed **17.3% of incorrect feature matches** and retained **96.7% of correct matches**. Judged precision rose from **28.4% to 31.6%**.

However, confirmed events reached with at least 20 correct correspondences fell from **13/17 to 12/17**. The experiment demonstrates cleaner feature assignments with a coverage trade-off. It does not demonstrate an improvement on every end-to-end objective. Keep confidence 0.3 when retaining loop opportunities is the priority; confidence 0.4 remains a separate experimental configuration. Existing benchmark configurations were not switched.

## Fresh test: all three OldTownFall trajectories

458 sampled frames; identical chronological images, K=5 and five-second temporal exclusion. Each method returned 2,107 candidate image pairs. No choice was changed using this test.

| Measurement | ORB + DBoW2 | Baseline LDO (0.3) | Selected LDO (0.4) |
| --- | ---: | ---: | ---: |
| Correct feature matches | 791 | 40003 | 38673 |
| Incorrect feature matches | 5689 | 100983 | 83526 |
| Unknown feature matches | 2298 | 9879 | 8457 |
| Correct among judgeable features | 12.2% | 28.4% | 31.6% |
| Judgeable feature coverage | 73.8% | 93.5% | 93.5% |
| Reference-positive candidate pairs | 139 | 262 | 262 |
| Reference-negative candidate pairs | 966 | 477 | 477 |
| Unknown candidate pairs | 1002 | 1368 | 1368 |
| Confirmed events reached by raw retrieval | 11/17 | 17/17 | 17/17 |
| Confirmed events with >=20 correct matches | 2/17 | 13/17 | 12/17 |
| Usable reference-positive pairs | 9/139 | 192/262 | 188/262 |

Feature matches and candidate image pairs are different measurements. A reference-negative pair can still share some valid features below the required overlap. Unknowns are not false positives. Feature precision pools matches and is conditional on judgeable evidence; methods have unequal match density and reference coverage. Fresh full-pipeline methods retrieve their own image pairs; fixed development pairs isolate matching.

ORB uses the pinned upstream ORB extractor and DBoW2 retrieval. Its feature correspondence baseline is mutual Hamming matching with a 0.75 ratio test. This is a component benchmark, not the complete ORB-SLAM3 loop acceptance pipeline.

The 20-correct-match rule is an external evaluation diagnostic. Neither detector receives these verdicts, reference depth, semantic masks or ground-truth poses. No geometric solver or SLAM backend is executed by this experiment, so these counts are not accepted SLAM loop constraints.

### Per-trajectory diagnostic

| Trajectory | Reference events | ORB raw / usable | Baseline raw / usable | Selected raw / usable |
| --- | ---: | ---: | ---: | ---: |
| P000 | 2 | 2 / 0 | 2 / 2 | 2 / 2 |
| P001 | 7 | 3 / 0 | 7 / 4 | 7 / 3 |
| P002 | 8 | 6 / 2 | 8 / 7 | 8 / 7 |

### Why one event was lost

On P001, the confirmed event at **63.5 s** has one retrieved reference-positive pair, connecting to the image at **58.0 s**. Raising confidence changes its matches as follows:

| Confidence | Correct | Incorrect | Unknown | Meets the 20-correct-match diagnostic |
| --- | ---: | ---: | ---: | --- |
| 0.3 | 20 | 90 | 4 | Yes |
| 0.4 | 19 | 71 | 1 | No |

It discards 19 incorrect matches and one correct match. That single correct match crosses the diagnostic boundary. It does not establish a physical SLAM failure or justify retuning the diagnostic to hide the loss. Test settings remain frozen.

## Development and step decisions

880 identical image pairs: 560 fit and 320 validation. Fit and validation use different trajectories within AbandonedFactory2 and DesertGasStation. These previously inspected environments are development data. The predeclared promotion rule requires, per scene and pooled, at least 90% original correct matches, at least 95% original usable positive pairs, nondecreasing judged precision, and fewer incorrect matches than the previous selection.

| Stage | Outcome | Reason |
| --- | --- | --- |
| Confidence 0.3 / 0.4 / 0.5 / 0.6 | Select 0.4 | Higher thresholds fail fit retention in the desert scene. 0.4 passes validation. |
| Full-depth LightGlue | Keep adaptive | Full depth produces more incorrect matches than adaptive 0.4. |
| 512 / 1024 / 2048 features | Keep 1024 | 512 loses too many correct matches; 2048 increases incorrect matches. |
| 480 / native 640 / 960 resolution | Keep native | 480 loses correct matches and precision; 960 loses correct-match retention and judgeable coverage. |
| ALIKED-n16 + compatible LightGlue | Keep SuperPoint | ALIKED improves conditional precision, but usable-positive-pair retention in the desert falls below the required floor. |

ALIKED is a useful unsuccessful experiment: fit desert usable pairs fall from 64 to 59; validation falls from 43 to 36. Its validation judged precision is 55.6%, but coverage is 60.8% versus the baseline 83.4%. Conditional precision alone cannot establish superior matching.

### Validation results for every tested configuration

All rows use the same 320 image pairs, including zero-match pairs; 128 pairs are reference-positive.

| Configuration | Correct | Incorrect | Unknown | Judged precision | Judgeable coverage | Usable positive pairs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| superpoint / 1024 / native / adaptive / 0.3 | 13,360 | 20,845 | 6,801 | 39.1% | 83.4% | 104/128 |
| superpoint / 1024 / native / adaptive / 0.4 | 12,934 | 17,806 | 6,282 | 42.1% | 83.0% | 102/128 |
| superpoint / 1024 / native / adaptive / 0.5 | 12,452 | 15,279 | 5,782 | 44.9% | 82.7% | 102/128 |
| superpoint / 1024 / native / adaptive / 0.6 | 11,888 | 13,110 | 5,260 | 47.6% | 82.6% | 101/128 |
| superpoint / 1024 / native / full / 0.4 | 13,296 | 18,461 | 6,321 | 41.9% | 83.4% | 103/128 |
| superpoint / 512 / native / adaptive / 0.4 | 7,122 | 9,602 | 3,283 | 42.6% | 83.6% | 98/128 |
| superpoint / 2048 / native / adaptive / 0.4 | 19,101 | 26,049 | 9,104 | 42.3% | 83.2% | 107/128 |
| superpoint / 1024 / 480 / adaptive / 0.4 | 6,481 | 10,960 | 10,662 | 37.2% | 62.1% | 85/128 |
| superpoint / 1024 / 960 / adaptive / 0.4 | 10,390 | 9,907 | 15,740 | 51.2% | 56.3% | 102/128 |
| aliked / 1024 / native / adaptive / 0.4 | 12,266 | 9,802 | 14,199 | 55.6% | 60.8% | 99/128 |

## Implementation

- Replaceable `superpoint_lightglue` and `aliked_lightglue` adapters, compatible pretrained weights and descriptor fingerprints.
- Optional extraction resize preserving original image pixels and sizes. Production `build_pair_engine` reuses matching without loading retrieval.
- Dedicated task modules for installation, deterministic shared pairs, cached extraction/matching, cumulative promotion gates, fresh inference and independent scoring.
- Original model roots and configs are preserved. The selected config is [`optimized-matching.yaml`](../ldo/configs/optimized-matching.yaml).
- Source/config/model/dataset/evidence hashes and per-match NPZ artifacts support audit and resume. Changed source/configuration cannot be mixed into the frozen experiment.
- Dated Markdown/JSON reports use the existing FIFO evaluation file handler.

## Verification

- Full WSL suite: **202 passed, 19 subtests passed**. Targeted Ruff check and format check passed (20 files).
- Live threshold parity passed on four development pairs, including a zero-match result.
- On all **458 fresh queries and 2,107 pairs**, baseline and selected retrieval IDs/ranks/scores are identical, extracted feature coordinates are identical, and selected assignments exactly equal baseline assignments filtered at confidence >0.4.
- Independent geometry implementation and numerical tolerance configuration are unchanged. New scene assets conservatively exclude uninterpretable semantic classes; unmapped pixels remain unknown.
- Windows suite: one existing native-process cleanup test failed with `WinError 32` (a file lock). The same suite passes in WSL, where the actual native/GPU experiments ran. No broad legacy-process changes were made for this matching task.

## Limits and next experiment

Only one fresh synthetic environment was tested. Pretraining exposure is unaudited. Incomplete pair labels withhold an overall recall claim, and unknown evidence is not negative supervision. No latency optimization, dedicated training, transform fitting, downstream trajectory evaluation or full SLAM integration was performed.

An appropriate subsequent experiment would test observation-only adaptive matching budgets or confidence policies on new development data, with an explicit event-retention objective. The fixed OldTownFall results must remain test evidence; do not tune the model or evaluator on the lost event.

## Artifacts and reproduction

- [Predeclared plan](ldo-matching-optimization-plan.md)
- [Task guide and commands](../evaluation/src/tasks/matching_optimization/README.md)
- [Complete generated report](ldo-matching-optimization-report.md)
- [Direct numerical results, manifests and runtime audits](ldo-matching-optimization-results.json)
- [Raw FIFO report JSON](ldo-matching-optimization-report.json)

Local raw artifact root: `/opt/loop-detector/experiments/matching_optimization`.

Pair-list SHA256: `3ec31808f210f2b5564b92e0c296e46cf3d06fe1be818c4cb9041d9ac1f2b93a`.

Experiment freeze SHA256: `2f4401a8256f9d6fe6fbd409a985360f935516a37a6367e1fcbc8cb1c916e0db`.

Fresh test results SHA256: `13440759fc840f7c4f4052e2453e6df844845ef7283bf008fb56921803731d90`.
