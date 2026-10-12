# Reference-depth evaluator v2: completed results

Completed 2026-10-10. All saved correspondences from 11 trajectories in
AbandonedFactory2 and DesertGasStation were replayed: 136,679 ORB matches and
1,091,985 LDO matches. Neither model nor matching was rerun or tuned. Original
reports and both original XYZ/reference-geometry implementations are unchanged.

## What changed

The new version accepts positive finite scene depths without the old 0.25–50 m
range restriction. Official semantic masks identify sky independently of distance.
It samples inverse depth from the active subpixel footprint instead of rejecting
features because of unrelated 3×3 neighbours. Mixed-depth active footprints remain
unknown. Existing XYZ and symmetric reprojection tolerances are unchanged.

## Results

| Environment | Method | Coverage before | Coverage after | Correct among judgeable before | Correct among judgeable after |
| --- | --- | ---: | ---: | ---: | ---: |
| AbandonedFactory2 | ORB | 47.2% | 51.4% | 25.8% | 25.4% |
| AbandonedFactory2 | LDO | 48.8% | 86.3% | 40.8% | 37.3% |
| DesertGasStation | ORB | 7.8% | 12.3% | 25.1% | 22.0% |
| DesertGasStation | LDO | 18.1% | 45.3% | 33.6% | 23.9% |
| Combined | ORB | 22.0% | 26.4% | 25.6% | 24.4% |
| Combined | LDO | 39.9% | 74.4% | 39.8% | 34.9% |

| Combined feature verdicts | ORB before | ORB after | LDO before | LDO after |
| --- | ---: | ---: | ---: | ---: |
| Correct | 7,689 | 8,788 | 173,653 | 283,540 |
| Incorrect | 22,333 | 27,277 | 262,237 | 528,998 |
| Unknown | 106,657 | 100,614 | 656,095 | 279,447 |

LDO has 109,887 previously unknown matches newly judged correct and 266,762 newly
judged incorrect. One previously incorrect match becomes unknown due to semantic
sky. All previously supported LDO matches remain supported. ORB has 838 unknowns
newly correct and 5,205 newly incorrect; sampling also changes 600 previously
incorrect matches to correct and 339 previously correct matches to incorrect.

## What the audit revealed

The previous range-failure category combined true distant surfaces with finite
sky depths and neighbouring depth discontinuities. It did not establish that all
those matches could be evaluated simply by increasing 50 m.

After rescoring, 279,447 LDO matches remain unknown, all because at least one active
endpoint footprint contains sky. ORB has 97,575 sky unknowns and 3,039 ambiguous
depth-boundary unknowns. No missing depth-file or pose failures occurred.

46,541 LDO matches and 1,585 ORB matches are now judged at maximum endpoint depth
above 50 m. Most of LDO's additional coverage comes from usable samples at depths
up to 50 m that the original neighbourhood checks excluded. Removing the range
restriction alone would not have produced the observed gain.

## Interpretation

The evaluator now judges considerably more LDO evidence and modestly more ORB
evidence. Both conditional precision scores decline because many previously
unknown matches are incorrect. LDO remains higher on judged correspondence
precision in both scenes, but the outdoor difference is small and coverage differs.
This is not improved model accuracy: the model outputs are identical.

Sky should remain unknown for physical world-point correspondence checks. Sky
texture can still support an angular/rotation-only observation, which would be
a separate assessment rather than a physical XYZ match.

This revision was designed after inspecting the test results and is not fresh
held-out evidence. The sampler treats reported pixel coordinates as exact sampling
locations; feature-localization uncertainty near boundaries is not fully modeled.
Controlled positives and negatives verify implementation behavior, not the
physical correctness of every real correspondence. Keep unknowns separate.

Image-pair overlap labels and confirmed-event counts were not recomputed: the
previous LDO 48/53 and ORB 42/53 retrieval results still use the original pair
reference policy. This work establishes no accepted-loop or trajectory improvement.

## Artifacts

- [Implementation plan](reference-depth-v2-plan.md)
- [Task instructions](../evaluation/src/tasks/reference_depth_v2/README.md)
- [Full generated report](reference-depth-v2-report.md)
- [Generated JSON report](reference-depth-v2-report.json)
- Dated original: `evaluation/output/comparison_2026-10-10_15-47-46_496592_05655bd1.{json,md}`.
- Latest pointer: `evaluation/output/reference_depth_v2.json`.
- Raw per-feature evidence and source snapshots: under `/opt/loop-detector/experiments/reference_depth_v2/` in WSL.

Validation: the full suite passed 191 tests with two skips and 19 subtests before
adding the saved-evidence integration case; all 10 focused v2 tests then passed.
Original EuRoC XYZ and original reference geometry hashes match their frozen values.
