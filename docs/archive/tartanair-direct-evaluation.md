# Direct TartanAir evaluation of model outputs

## Decision
The default TartanAir experiment measures feature correspondences against simulator reference geometry. It does not run our learned stereo estimator or shared operational verifier. The prior full-pipeline experiment remains available explicitly through `pipeline`; its pose-error counts are not part of this model measurement. The original EuRoC XYZ evaluator is unchanged.

## Calculation
For each original reported feature pair `(u_q, v_q) <-> (u_h, v_h)`:

```text
p_camera = Z_reference * inverse(K) * [u, v, 1]
p_world_query = T_world_query_camera * p_query_camera
p_world_history = T_world_history_camera * p_history_camera
world_distance = norm(p_world_query - p_world_history)
```

Both points must have usable reference depth. Support requires world distance <= `max(0.05 m, 0.005 * max(Z_query, Z_history))` and symmetric reference-pose reprojection error <=3 pixels. These are frozen measurement tolerances. Camera poses and reference depth never enter either detector. All original assignments are included; no previous pose decision, inlier selection or operational acceptance gate filters the observations.

Supported means both checks pass. Contradicted means usable reference depths disagree under these checks. Unknown means at least one endpoint has no usable reference depth, including local depth boundaries or depth outside 0.25-50 m. Unknown is not a false correspondence. Each feature row retains the original IDs and pixels, both world coordinates when valid, validity flags, numerical errors and verdict.

## Direct measurement on the frozen detector outputs

All seven trajectories and all 453 candidates per method are included:

| Feature result | ORB + DBoW2 baseline | LDO |
| --- | ---: | ---: |
| Reported matches | 3,620 | 35,542 |
| Reference-supported | 777 | 7,972 |
| Reference-contradicted | 1,609 | 9,007 |
| Unknown | 1,234 | 18,563 |
| Judgeable fraction | 65.9% | 47.8% |
| Supported among judgeable | 32.6% | 47.0% |
| Contradicted among judgeable | 67.4% | 53.0% |
| Supported fraction bounds across all matches | 21.5%-55.6% | 22.4%-74.7% |

These are the same independent feature measurements that existed in the previous report, now recomputed directly from original assignments and presented separately from stereo/pose-verifier failures. This change isolates what we measure; it does not change model weights, detector outputs or reference thresholds.

LDO supplies more supported correspondences and has a higher supported fraction in the judgeable subset. It also supplies more contradicted correspondences in absolute terms because it reports many more matches. Unequal unknown coverage means these subset rates do not establish accuracy over all reported matches. Their all-match bounds overlap.

## Separate candidate-pair measurement
Independent surface-overlap labels classify the image pair, not its individual matches. ORB returns 53 overlap-positive, 347 overlap-negative and 53 unknown candidates; LDO returns 61, 324 and 68 respectively. Both retrieve candidates for all ten confirmed event runs at K=5. Overall recall remains unavailable because the reference universe is incomplete. An overlap-negative label uses the frozen 20% shared-surface definition; it does not prove that no correct features can be matched in a smaller shared region.

## Verification
Tests exercise real packed reference depth, camera/world transforms and all three feature outcomes. An integration test deliberately makes previous operational decision files unreadable and forbids constructing the stereo estimator and verifier; direct evaluation still checks every assignment. Tampered detector traces and partial sequence evidence fail. A fresh image-only detector run exercises the new default path separately from the saved-output rescore.

## Commands

```powershell
# Original detector outputs, recomputed directly:
uv run python evaluation/reference_geometry.py evaluate --results evaluation/output/tartanair_benchmark_5f0f638b30a442d4b6673677234c332d/summary.json
# New detector outputs, same frozen reference protocol:
uv run python evaluation/reference_geometry.py run --prepared evaluation/output/tartanair_reference_40e62aa6cbf74f70bc0dd733e99e1b13
```

The short synthetic environment, static-world assumption, unknown depth boundaries and unaudited pretrained training overlap remain limitations. These results do not establish long-term loop-closure performance or real-world superiority.

## Completed execution artifacts

Fresh image-only inference reproduced every aggregate count from the saved-output rescore exactly. Final report: `evaluation/output/comparison_2026-10-09_18-09-31_019938_54b2f5f8.md` (and companion JSON). Source detector evidence: `/mnt/c/Users/elayb/OneDrive/Documents/visual–IMU loop detector/evaluation/output/tartanair_detector_evidence_a873fd45e6ef45c6b8ea6e388e2b4587`. Direct evaluation evidence: `/mnt/c/Users/elayb/OneDrive/Documents/visual–IMU loop detector/evaluation/output/tartanair_reference_features_0165e67a713d493bbc9f726ea7820851`. The full suite passed 176 tests, with one skipped and 19 subtests; lint passed. The report also appears as `.docs/tartanair-direct-report.md`.
