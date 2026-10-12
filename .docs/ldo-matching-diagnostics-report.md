# LDO matching failure diagnosis

Baseline events with >=20 correct matches: **13/17**.

All original model outputs and XYZ verdicts are preserved. OldTownFall is used for post-test explanation only. Oracle associations are never model inputs.

## Four weak events

| Trajectory | Event start (s) | Retrieved positive pairs | Best reported correct | Maximum capacity of existing features | Finding |
| --- | ---: | ---: | ---: | ---: | --- |
| P001 | 13.00 | 1 | 0 | 2 | Existing feature capacity is insufficient |
| P001 | 14.00 | 14 | 7 | 20 | Supported associations remain unused |
| P001 | 43.50 | 14 | 3 | 37 | Supported associations remain unused |
| P002 | 11.50 | 1 | 8 | 46 | Supported associations remain unused |

Maximum capacity is the largest one-to-one assignment between the existing keypoints that passes the unchanged XYZ/reprojection evaluator. Best reported and maximum capacity are each maxima over the event's retrieved positive pairs; they can occur on different pairs.

It is an evaluator upper bound, not evidence that a visual matcher can uniquely recover every edge or that a SLAM backend can accept the loop.

Across these 30 pairs: 30 reported supports, 363 contradictions and 27 unknowns. Of the contradictions, 27 lie within twice both numerical gates; 336 have larger residuals. The near-gate diagnostic never relabels a failed match.

## Independent development check

Only the pre-existing fixed reference-positive development pairs are analyzed. These are separate factory/desert trajectories, not the four OldTownFall examples. Zero-match pairs remain included.

| Split / scene | Positive pairs | Currently usable | Existing-feature oracle usable | Assignment-gap pairs | Capacity-limited pairs |
| --- | ---: | ---: | ---: | ---: | ---: |
| fit / overall | 224 | 181 | 224 | 43 | 0 |
| fit / AbandonedFactory2 | 128 | 117 | 128 | 11 | 0 |
| fit / DesertGasStation | 96 | 64 | 96 | 32 | 0 |
| validate / overall | 128 | 104 | 128 | 24 | 0 |
| validate / AbandonedFactory2 | 64 | 61 | 64 | 3 | 0 |
| validate / DesertGasStation | 64 | 43 | 64 | 21 | 0 |

## Detailed pair evidence

### P001 / revisit_13000000000

| Query / history (s) | Correct / incorrect / unknown | Oracle capacity | Valid-depth query / history features | Query features projecting inside history | Unmatched features with supported alternatives | Median rejected pixel error |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 13.00 / 8.00 | 0 / 1 / 0 | 2 | 1021 / 1018 | 21 | 2 | 365.96 px |
### P001 / revisit_13999999488

| Query / history (s) | Correct / incorrect / unknown | Oracle capacity | Valid-depth query / history features | Query features projecting inside history | Unmatched features with supported alternatives | Median rejected pixel error |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 14.00 / 8.00 | 0 / 2 / 0 | 2 | 1023 / 1018 | 29 | 2 | 174.23 px |
| 14.00 / 8.50 | 0 / 4 / 0 | 1 | 1023 / 1021 | 30 | 1 | 371.73 px |
| 14.50 / 9.00 | 0 / 6 / 1 | 2 | 1023 / 1021 | 40 | 2 | 1.88 px |
| 14.50 / 8.00 | 0 / 1 / 0 | 1 | 1023 / 1018 | 31 | 1 | 287.04 px |
| 14.50 / 9.50 | 0 / 45 / 0 | 7 | 1023 / 1020 | 57 | 7 | N/A |
| 14.50 / 8.50 | 0 / 4 / 2 | 0 | 1023 / 1021 | 33 | 0 | 118.63 px |
| 15.00 / 10.00 | 4 / 11 / 2 | 15 | 1015 / 1020 | 68 | 11 | 18.94 px |
| 15.00 / 8.50 | 2 / 4 / 2 | 18 | 1015 / 1021 | 57 | 15 | 7.33 px |
| 15.00 / 8.00 | 0 / 0 / 0 | 2 | 1015 / 1018 | 40 | 2 | N/A |
| 15.50 / 9.00 | 0 / 1 / 1 | 0 | 1015 / 1021 | 31 | 0 | N/A |
| 15.50 / 10.00 | 0 / 2 / 1 | 2 | 1015 / 1020 | 40 | 2 | 487.14 px |
| 15.50 / 8.00 | 0 / 0 / 0 | 3 | 1015 / 1018 | 33 | 3 | N/A |
| 15.50 / 8.50 | 2 / 6 / 3 | 2 | 1015 / 1021 | 36 | 0 | 22.23 px |
| 16.00 / 8.50 | 7 / 29 / 2 | 20 | 1012 / 1021 | 89 | 11 | 48.43 px |
### P001 / revisit_43500001792

| Query / history (s) | Correct / incorrect / unknown | Oracle capacity | Valid-depth query / history features | Query features projecting inside history | Unmatched features with supported alternatives | Median rejected pixel error |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 43.50 / 38.50 | 0 / 3 / 0 | 11 | 1018 / 945 | 588 | 11 | 49.84 px |
| 44.00 / 38.50 | 0 / 5 / 0 | 16 | 1022 / 945 | 571 | 16 | 154.67 px |
| 44.50 / 38.50 | 0 / 3 / 1 | 13 | 1022 / 945 | 547 | 13 | 247.67 px |
| 44.50 / 39.00 | 0 / 8 / 0 | 12 | 1022 / 954 | 598 | 11 | 47.99 px |
| 45.00 / 39.00 | 0 / 9 / 0 | 9 | 1018 / 954 | 594 | 8 | 61.10 px |
| 45.00 / 39.50 | 0 / 8 / 0 | 5 | 1018 / 933 | 518 | 5 | 92.06 px |
| 45.00 / 38.50 | 0 / 0 / 1 | 6 | 1018 / 945 | 543 | 6 | N/A |
| 45.50 / 39.50 | 0 / 25 / 2 | 13 | 1008 / 933 | 607 | 13 | 94.66 px |
| 45.50 / 38.50 | 0 / 5 / 0 | 10 | 1008 / 945 | 633 | 10 | 549.31 px |
| 45.50 / 39.00 | 0 / 15 / 0 | 13 | 1008 / 954 | 680 | 13 | 78.56 px |
| 46.00 / 40.50 | 2 / 20 / 2 | 25 | 1008 / 953 | 593 | 23 | 73.93 px |
| 46.00 / 39.00 | 0 / 5 / 0 | 17 | 1008 / 954 | 684 | 17 | 92.67 px |
| 46.50 / 41.00 | 2 / 20 / 2 | 37 | 1013 / 943 | 538 | 34 | 97.78 px |
| 47.00 / 41.50 | 3 / 27 / 0 | 29 | 1023 / 958 | 348 | 26 | 51.77 px |
### P002 / revisit_11499999744

| Query / history (s) | Correct / incorrect / unknown | Oracle capacity | Valid-depth query / history features | Query features projecting inside history | Unmatched features with supported alternatives | Median rejected pixel error |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 11.50 / 6.00 | 8 / 94 / 5 | 46 | 985 / 981 | 651 | 36 | 13.04 px |

## Interpretation and next experiment

Prioritize association quality and low-overlap handling. Most failed matches in these events have large residuals, and three events have enough existing geometrically supported feature alternatives. Missing reference evidence and small localization errors do not explain most of these observed contradictions.

The capacity-limited event also needs better observations, extraction or candidate selection. Its low capacity is conditional on the fixed keypoints, visibility and evaluator; it does not prove a specific detector defect.

A stronger image-pair transformer is the next candidate experiment. Choose its settings on development data, require fewer incorrect matches and preservation of every baseline usable event ID on full fit/validation replays, then freeze and test on a new environment. No alternative model is adopted by this diagnostic task.

## Reproduction and limits

Run `python -m tasks.matching_diagnostics run` in the installed WSL environment with `PYTHONPATH=.:evaluation/src`. `check` returns exit code 2 while the saved baseline remains below the all-events diagnostic target; this is expected, not a tool failure.

Reference projection alone checks field of view, not occlusion. Oracle edges additionally pass the complete frozen bidirectional depth/XYZ/reprojection test. Counts describe repeated image correspondences, not distinct world landmarks. No pose fitting, RANSAC, model training, reference-guided inference or tolerance relaxation is performed.

Artifacts: `/opt/loop-detector/experiments/matching_diagnostics/v1`

Original test SHA256: `13440759fc840f7c4f4052e2453e6df844845ef7283bf008fb56921803731d90`

Analysis freeze identity: `2e86c73d3f295eb64da8d53e4b66bdbc53d4e2674626725542102755386cb5f5`
