# Frozen LDO testing on two unused TartanAir environments

Completed 2026-10-10. All 11 Data_easy trajectories were installed and tested:
AbandonedFactory2 P000–P005 and DesertGasStation P000–P004, totaling 1,486 sampled
frames. Selection was recorded before model outcomes. Approximately 8.13 GB of
compressed stereo images, left depth, poses and IMU archives were downloaded and
verified against upstream SHA256 values.

## Setup

The frozen confidence-only configuration uses MegaLoc retrieval and SuperPoint +
LightGlue matching with confidence 0.3. No training, adapted weights, candidate
filtering or threshold tuning was performed on these scenes. ORB + DBoW2 uses the
existing pinned native implementation. Both receive identical grayscale images,
approximately 2 Hz, five candidates per eligible query, and a five-second temporal
exclusion; retrieval history resets between trajectories.

The evaluator uses independent simulator depth and camera poses. Correct candidate
pairs meet the frozen 20% minimum bidirectional visible-overlap rule; this is not
a count of accepted SLAM loop constraints. Event hits measure retrieval only.
Every original feature assignment is checked separately against frozen XYZ and
reprojection tolerances. Neither detector receives ground truth or IMU. The
original EuRoC XYZ implementation and configuration are unchanged.

## Candidate retrieval

| Environment | Detector | Correct pairs | False pairs | Unknown pairs | Confirmed event hits |
| --- | --- | ---: | ---: | ---: | ---: |
| AbandonedFactory2 | ORB + DBoW2 | 651 | 1,760 | 1,188 | 23/29 |
| AbandonedFactory2 | LDO | 1,351 | 830 | 1,418 | 27/29 |
| DesertGasStation | ORB + DBoW2 | 224 | 984 | 1,952 | 19/24 |
| DesertGasStation | LDO | 352 | 756 | 2,052 | 21/24 |
| Combined | ORB + DBoW2 | 875 | 2,744 | 3,140 | 42/53 |
| Combined | LDO | 1,703 | 1,586 | 3,470 | 48/53 |

Both methods returned 6,759 candidate pairs. On the judged labels, LDO returned
94.6% more correct pairs and 42.2% fewer false pairs overall. Precision among known
candidate labels is 51.8% for LDO and 24.2% for ORB. Including unknown candidates,
precision bounds are 25.2–76.5% and 12.9–59.4%, respectively; these ranges overlap.
Unknowns are neither correct nor false. Confirmed reference event runs are not
necessarily independent physical revisits, and incomplete reference labels
prevent an overall recall claim.

## Feature correspondence quality

| Environment | Detector | Correct | Incorrect | Unknown | Correct among judgeable | Judgeable coverage |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| AbandonedFactory2 | ORB + DBoW2 | 5,974 | 17,214 | 25,985 | 25.8% | 47.2% |
| AbandonedFactory2 | LDO | 154,417 | 224,291 | 396,982 | 40.8% | 48.8% |
| DesertGasStation | ORB + DBoW2 | 1,715 | 5,119 | 80,672 | 25.1% | 7.8% |
| DesertGasStation | LDO | 19,236 | 37,946 | 259,113 | 33.6% | 18.1% |
| Combined | ORB + DBoW2 | 7,689 | 22,333 | 106,657 | 25.6% | 22.0% |
| Combined | LDO | 173,653 | 262,237 | 656,095 | 39.8% | 39.9% |

LDO's judged feature precision is higher in both environments, but the absolute
rates remain low. LDO emits many more assignments, including many more incorrect
assignments; a better error rate does not mean fewer total bad features. These
measurements use each detector's own candidate pairs and do not isolate the
matcher from retrieval. Unknown-inclusive feature correctness bounds overlap:
15.9–76.0% for LDO and 5.6–83.7% for ORB overall.

### Why reference checks abstained

Each unknown match receives one primary reason; range failures take priority over
boundary failures when both endpoints differ. No missing-pose or synchronization
failure occurred in these counts.

| Environment | Detector | Depth outside 0.25–50 m | Depth boundary |
| --- | --- | ---: | ---: |
| AbandonedFactory2 | ORB + DBoW2 | 23,499 | 2,486 |
| AbandonedFactory2 | LDO | 310,490 | 86,492 |
| DesertGasStation | ORB + DBoW2 | 77,970 | 2,702 |
| DesertGasStation | LDO | 228,849 | 30,264 |

The range category means at least one value in an endpoint's 3×3 depth patch is
outside the allowed interval. Boundary means the patch exceeds the frozen 5%
depth-spread tolerance. The depth range category does not distinguish near from
far violations. Gates were not relaxed after seeing these results.

## Conclusion

The frozen LDO improves candidate retrieval and judged correspondence quality
relative to ORB + DBoW2 in both new environments. This supports continuing its
development. It does not establish accuracy across unknown matches, universal
superiority, real-world generalization, accepted loop quality, latency or improved
SLAM trajectories. These scenes were unused in our own development; upstream
pretraining exposure and shared synthetic assets remain unaudited.

Keep this configuration frozen for subsequent tests. Investigate low feature
precision and reference coverage in a separate development experiment; do not
retune on these held-out results and reuse them as fresh test evidence.

## Reproducibility

- [Frozen plan](ldo-unseen-tartanair-plan.md)
- [Task and commands](../evaluation/src/tasks/unseen_tartanair/README.md)
- [Full generated report](ldo-unseen-tartanair-report.md), including per-trajectory results
- [Machine-readable results](ldo-unseen-tartanair-results.json)
- Project dated report: `evaluation/output/comparison_2026-10-10_15-34-28_537608_c83b16a7.{json,md}`.
- Raw datasets: `/opt/loop-detector/datasets/tartanair_unseen/` in WSL.
- Raw reference and detector evidence: `/opt/loop-detector/experiments/tartanair_unseen/` in WSL.

The first combined report attempt used a renderer loaded before this task's route
was added. Publishing in a fresh process succeeded from the saved results, without
rerunning inference or changing measurements. The full test suite passed with
182 tests, two skips and 19 subtests; task lint checks passed.
