# TartanAir V2 pilot results - 2026-10-09

## Completed
Installed and hash-verified five pinned archives (1.415 GB compressed): front left/right images, front left/right depth and IMU, including both camera poses. Ran all seven ArchVizTinyHouseDay/Data_easy trajectories, 176 sampled frames and 906 raw candidate proposals total (453 per method). Prepared the complete temporal pair universe before either detector ran. Both models received identical grayscale frames, with separate reference-only depth/poses and shared observation-based geometric verification. The original XYZ implementation and configuration hashes remain unchanged.

## Main results

| Measurement | ORB + DBoW2 | LDO-MegaLoc-LightGlue |
| --- | ---: | ---: |
| Raw candidate pairs (K=5) | 453 | 453 |
| Overlap-positive / negative / unknown candidates | 53 / 347 / 53 | 61 / 324 / 68 |
| Accepted camera-derived constraints | 40 | 142 |
| Accepted, relative pose within 0.20 m / 5 degrees | 39 | 117 |
| Accepted, relative pose outside tolerance | 1 (2.5%) | 25 (17.6%) |
| Accepted, overlap-positive AND pose within tolerance | 28 | 57 |
| Confirmed event runs reached by those constraints | 9 / 10 | 10 / 10 |
| Reference-supported feature correspondences | 777 | 7,972 |
| Reference-contradicted feature correspondences | 1,609 | 9,007 |
| Untestable feature correspondences | 1,234 | 18,563 |
| Judgeable feature coverage | 65.9% | 47.8% |

The final reference contains **10 confirmed event runs**, correcting the earlier progress update that said 11. These are contiguous confirmed overlap-positive query runs, not a certified total of all physical revisit events.

## What this establishes
LDO found more constraints satisfying both independent overlap and pose checks on this pilot (57 versus 28), and reached one additional confirmed event run through those constraints. It also accepted more pose-inaccurate constraints: 25 versus 1. This supports a detection-yield improvement here, while demonstrating a substantial reliability issue in the full LDO plus shared-verifier pipeline. It does not justify an overall superiority claim.

Top-1 candidate precision bounds were 30.2%-38.7% for LDO versus 17.9%-27.4% for ORB under the frozen overlap definition. These bounds account for unknown labels; they are not statistical confidence intervals. At K=5 the precision bounds overlap. Both methods retrieved candidates for all 10 confirmed event runs at K=5, so repeated candidate returns must not be presented as additional distinct loop closures.

## Why some features remain unknown
The independent reference-depth audit reproduces every untestable verdict:

| First failing gate across either endpoint | ORB | LDO |
| --- | ---: | ---: |
| Depth outside 0.25-50 m | 413 | 6,941 |
| Depth boundary: local 3x3 depth spread >5% | 821 | 11,622 |
| Missing/nonfinite pixel or depth | 0 | 0 |

Thus the reference-depth coverage deficit here is caused by feature positions near depth discontinuities and outside the useful depth range. It is not a missing stereo-frame synchronization problem. These unknown matches cannot be classified as false correspondences. Per-feature numerical errors and original assignments are retained for inspection.

## Limits on interpretation
- This installed subset consists of short 9-15 second trajectories. The original 20-second exclusion produced no eligible pairs; a dedicated 5-second exclusion was fixed equally for both methods before detector inference. This is a short synthetic pilot, not a long-term loop-closure study.
- Overlap labels use a frozen 20% minimum bidirectional visible-surface overlap, with explicit uncertainty bounds. An overlap-negative accepted constraint can still connect a smaller shared region; it is not automatically a physically incorrect association.
- Pose error is measured independently against simulator camera poses. The 0.20 m / 5 degree limits are provisional evaluation tolerances, not calibrated publication thresholds or proof of a false revisit.
- Some pair references remain unknown, so overall recall is withheld. Confirmed-event hit counts cover the confirmed subset only.
- Feature counts use each detector's own returned candidates, extraction settings and actual assignments. They do not isolate matcher quality at a shared correspondence budget.
- Neither current detector consumes IMU. Static-world assumptions and pretrained dataset overlap are not independently certified. Real-world and OOD generalization remain untested.

## Artifacts
- Final dated report: `evaluation/output/comparison_2026-10-09_17-05-31_205949_ec69cfe8.md` and companion JSON.
- Raw evidence: `evaluation/output/tartanair_benchmark_5f0f638b30a442d4b6673677234c332d/`.
- Frozen reference: `evaluation/output/tartanair_reference_40e62aa6cbf74f70bc0dd733e99e1b13/`.
- Dataset index: `evaluation/datasets/tartanair_v2/installation.json`; physical data in WSL `/opt/loop-detector/datasets/tartanair_v2`.
- Protocol: `.docs/tartanair-reference-geometry-plan.md`.

## Next experiment
Use longer trajectories with meaningful temporal exclusion and a separate held-out environment. Freeze an operating-point selection protocol and compare jointly confirmed event detection at controlled accepted-constraint risk. Investigate the 25 LDO pose failures without changing the independent evaluator or declaring unknown cases false. These data motivate that work; they do not complete it.
