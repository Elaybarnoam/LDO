# Independent revisit evaluation: implementation and results

Date: 2026-10-07. Sequence: EuRoC MH_01_easy (development).

## Implemented workflow

Full eligible reference universe → detector-blind scene review → independent reviewer consensus → immutable reference snapshot → continuous revisit events → equal candidate-budget evaluation → development threshold selection → frozen held-out evaluation → dated Markdown/JSON reporting.

Ground-truth poses propose review regions; they do not assign correct-loop labels. Opportunities missed by both detectors remain in the universe. Unknown decisions stay unknown. External XYZ calculations and thresholds are unchanged. Positive and hard-negative decisions require two distinct agreeing reviewers.

## Actual run

The reference contains 52,326 eligible image pairs, 363 pose-admitted query frames, and 323 queries with eligible history. Six queries were excluded for missing reference poses. Review aids proposed 10,769 pairs in two continuous query intervals.

| Measurement | ORB + DBoW2 | LDO |
| --- | ---: | ---: |
| Returned candidate pairs, K=1 | 310 | 281 |
| Returned candidate pairs, K=5 | 1,540 | 1,512 |
| Shared geometric verifier accepted | 454 | 1,071 |
| Accepted estimates within provisional reference pose tolerance | 423 | 929 |
| External XYZ supported feature observations | 22,309 | 186,611 |
| External XYZ contradicted feature observations | 2,286 | 6,224 |
| External XYZ unknown feature observations | 30,107 | 260,995 |
| External XYZ judgeable coverage | 44.96% | 42.49% |

These secondary measurements reuse the existing full verifier/XYZ evidence and reconcile against the new complete reference. They count candidate pairs and feature observations, not independently confirmed loop events. Feature observations may repeat landmarks; candidate sets differ.

## What these results establish

The implemented workflow runs successfully and preserves existing evidence. LDO produces more accepted, pose-consistent candidate connections on this development sequence. This does not establish that LDO detects more distinct correct loops.

Independent scene reviews supplied: **0**. All 52,326 reference pair labels remain unknown. Correct-loop precision, overall event recall, and matched-precision operating points are therefore **unavailable**. The frozen snapshot is explicitly named `unreviewed_development_2026-10-07`. Zero confirmed events means the reference is unreviewed, not that the route has no loops.

## Remaining evidence work

1. Independently review the original-image intervals, including hard negatives and opportunities neither detector returned.
2. Freeze the reviewed development reference and select operating points at the declared shared precision target.
3. Run independently labeled held-out V1_01_easy and V2_01_easy with frozen settings and report per-sequence and aggregate outcomes.

The implementation provides commands and a detector-blind OpenCV review tool for these steps. Scientific scene decisions were not fabricated to complete the software run.

## Verification

Final full test suite: **135 passed, 1 skipped, 19 subtests passed**. New package lint and formatting checks passed. Real original-image review panels and navigation rendered without writing labels. One earlier suite run encountered a transient Windows native.log cleanup lock; its isolated rerun and the final full suite passed.

## Saved artifacts

- Plan: `.docs/independent-revisit-evaluation-plan.md`
- Task package and command guide: `evaluation/src/tasks/loop_closure/revisits/`
- Full reference: `evaluation/references/MH_01_easy_revisits_v1/`
- Frozen reference: `evaluation/references/MH_01_easy_revisits_v1/snapshots/unreviewed_development_2026-10-07/`
- Run report: `evaluation/output/comparison_2026-10-07_21-36-47_662451_491c2993.md`
- Machine report: same basename with `.json`
- Operating-point artifact: `evaluation/output/operating_points_5efbd5aabbff4148bc3c744cea335812.json` (explicitly unavailable because development labels are incomplete)