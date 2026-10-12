# LDO sequential optimization results

Experiment completed 2026-10-09. This is an initial synthetic evaluation, not a claim of general superiority over ORB or modern SLAM systems.

## Recommendation

**Use the confidence-only configuration for the next pilot:** `ldo/configs/optimized-confidence.yaml` (`match_threshold: 0.3`). It removed 32.5% of incorrect feature matches on the held-out environment while retaining 96.6% of correct feature matches and all confirmed event hits.

Keep candidate filtering experimental: it substantially reduced false candidate returns, but lost two confirmed event hits. Keep pretrained matcher weights: adaptation did not pass its development promotion check.

This recommendation interprets the completed test. It does not change frozen experiment parameters or establish performance on another independent dataset. `optimized.yaml` records the **pre-test development selection**, which included candidate filtering; it is not an unconditional deployment recommendation.

## Split and protocol

| Role | Environment | Trajectories |
| --- | --- | --- |
| Matcher training | RetroOffice | P000–P005 |
| Confidence/policy fitting | ArchVizTinyHouseDay | P000–P004 |
| Policy/checkpoint selection | ArchVizTinyHouseDay | P005–P006 |
| Held-out test | CountryHouse | P000–P005 |

CountryHouse contains 389 sampled frames, 1,579 raw candidate returns per detector, and 19 confirmed reference events. Sampling is approximately 2 Hz, temporal exclusion is 5 seconds, and the raw candidate budget is K=5. These remain short synthetic trajectories. Upstream pretraining exposure is unaudited.

All configurations and checkpoint choices were frozen before held-out model inference. No parameters were retuned on CountryHouse. The original XYZ evaluator and configuration were preserved. Direct simulator reference depth and camera poses judge matches independently, without stereo estimation, RANSAC, PnP or an operational verifier.

## Step 1: confidence filtering — useful improvement

The development-selected confidence threshold increased from 0.1 to 0.3.

| Held-out feature measurement | Baseline LDO | Confidence-only |
| --- | ---: | ---: |
| Correct matches | 146,270 | 141,287 |
| Incorrect matches | 66,687 | 45,003 |
| Unknown matches | 53,618 | 39,409 |
| Correct among judgeable matches | 68.7% | 75.8% |
| Judgeable fraction | 79.9% | 82.5% |
| Confirmed event hits | 19/19 | 19/19 |

This removes 21,684 incorrect matches (32.5%), losing 4,983 correct matches (3.4%). Retrieval is unchanged: 670 correct candidate pairs, 791 false candidates and 118 unknown pairs. **This step improves feature selection; it does not reduce the number of false image-pair candidates.**

## Step 2: candidate confidence — precision/coverage trade-off

A regularized logistic policy uses only image-derived retrieval and matching evidence. Ground truth supplies development labels, never runtime inputs.

| Held-out candidate measurement | Confidence-only | + Candidate policy |
| --- | ---: | ---: |
| Correct candidate pairs | 670 | 633 |
| False candidate pairs | 791 | 79 |
| Unknown candidate pairs | 118 | 88 |
| Total returned pairs | 1,579 | 800 |
| Confirmed event hits | 19/19 | 17/19 |

The policy removes 712 false candidates (90.0%) while retaining 94.5% of known correct candidate pairs. However, it retains only 89.5% of confirmed event hits, below its 90% retention target. Many retained pairs from the same event cannot compensate for losing a separate event.

Individual feature counts after this policy are 134,984 correct, 33,794 incorrect, and 34,916 unknown. Higher judged precision (80.0%) comes with reduced detection coverage. Do not describe this as an unqualified overall improvement.

## Step 3: assignment-head adaptation — not promoted

Training was real: 300 AdamW updates, seed 0, 144 reference-supervised training pairs and 66,049 trainable parameters. SuperPoint, MegaLoc and LightGlue transformer layers remained frozen. Supervision uses all selected feature combinations, one-to-one positive labels, unmatched dustbins, and ignored ambiguous/invalid reference evidence.

On development, the selected trained checkpoint had 777 incorrect and 1,572 correct matches. Its equal-compute pretrained control had the same 777 incorrect matches and 1,576 correct matches. It failed the promotion check and was not enabled. Serialized checkpoint reload reproduced assignments exactly.

The frozen experimental checkpoint was still tested on CountryHouse:

| Held-out measurement | Pretrained full-depth control | Trained assignment head |
| --- | ---: | ---: |
| Correct feature matches | 138,131 | 137,940 |
| Incorrect feature matches | 35,737 | 35,431 |
| Unknown feature matches | 37,052 | 36,731 |
| Correct among judgeable | 79.4% | 79.6% |
| Correct candidate pairs | 638 | 636 |
| False candidate pairs | 88 | 86 |
| Confirmed event hits | 18/19 | 18/19 |

Both rows use full-depth inference and the same confidence/candidate policy. The trained head removes 306 incorrect matches (0.9%) relative to this control but loses 191 correct matches and two correct candidate pairs. This is a small held-out change, not a robust training gain that reverses the failed development decision. Relative to the adaptive predecessor, the trained configuration produces 1,637 more incorrect matches; computation/configuration effects must not be attributed to learning.

## ORB comparison on the same held-out images

| Measurement | ORB + DBoW2 | Baseline LDO | Confidence-only LDO |
| --- | ---: | ---: | ---: |
| Correct candidate pairs | 497 | 670 | 670 |
| False candidate pairs | 1,011 | 791 | 791 |
| Unknown candidate pairs | 71 | 118 | 118 |
| Confirmed event hits | 19/19 | 19/19 | 19/19 |
| Correct feature matches | 14,161 | 146,270 | 141,287 |
| Incorrect feature matches | 7,856 | 66,687 | 45,003 |
| Unknown feature matches | 2,123 | 53,618 | 39,409 |
| Correct among judgeable | 64.3% | 68.7% | 75.8% |

Different numbers of assignments and unequal unknown coverage prevent interpreting absolute bad-match counts as error rates. Correct-match fraction bounds including unknowns overlap: ORB 58.7–67.5%, baseline LDO 54.9–75.0%, confidence-only 62.6–80.1%.

ORB is an unfiltered K=5 baseline. A fair claim about calibrated loop detectors also needs an equally calibrated ORB operating point and further independent environments. No latency or downstream SLAM trajectory improvement is established here.

## Definitions and evidence

Verification: the Windows suite passed 180 tests and 19 subtests (2 skipped). The model environment passed all 6 targeted optimization/supervision tests. A fresh production run on CountryHouse P000 reproduced 209 confidence-only candidate pairs (40,529 feature assignments) and 130 policy-filtered pairs (37,630 assignments). Candidate identities and feature indices matched offline evaluation exactly; confidence differences were <=1e-6. This check consumed only images/timestamps during inference.

- Correct feature match: both reference depths usable, symmetric reprojection <=3 px and XYZ distance <=max(0.05 m, 0.005 times maximum endpoint depth).
- Correct candidate: frozen minimum bidirectional visible surface overlap >=20%; false means the overlap upper bound is below 20%; uncertain cases remain unknown.
- Confirmed event hits: returns reaching independently confirmed reference event runs. Overall recall remains withheld where reference labels are incomplete.
- Original EuRoC XYZ code SHA256: `EB91C9C6320ABCF15A7726915370CA8D425B1E7301E9CF38F7BECDFCFC58B238`.
- Original EuRoC XYZ configuration SHA256: `FD8962D40C34EEC354E58BD5C3C9D3C9BC4C5181033826A203A8311B8E01AF81`.
- Frozen variant manifest SHA256: `f21980432b297b11939bae259b2dc810ca37d5a2bfd330291bd8a0d0c44a5495`.
- Dated shared-handler report: `evaluation/output/comparison_2026-10-09_18-52-02_629124_bd4f100a.md` and `.json`.
- Stage artifacts: `evaluation/output/optimization/development/` and `evaluation/output/optimization/heldout/`.
- [Experiment plan](ldo-sequential-optimization-plan.md), [training research](ldo-optimization-training-research.md), [reproduction guide](../evaluation/src/tasks/optimization/README.md).
