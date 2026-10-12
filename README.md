# LDO

LDO is a modular visual loop-detection approach with replaceable retrieval and feature-matching models. The current configuration is **LDO-MegaLoc-LightGlue**, using frozen pretrained MegaLoc, SuperPoint and LightGlue components.

The evaluation program compares LDO with the pinned upstream **ORB + DBoW2** detector. Independent reference evaluators assess reported feature correspondences, image-pair overlap and relative pose. Reference labels never enter either detector or the shared operational verifier.

## Default evaluation: direct TartanAir reference checks

The default TartanAir task checks every reported feature match using simulator reference depth and camera poses. It uses no learned stereo estimation, fitted pose or operational verifier. Candidate-pair overlap is evaluated independently. Unknown depth evidence remains unknown.

| Direct feature measurement | ORB + DBoW2 | LDO |
| --- | ---: | ---: |
| Reference-supported correspondences | 777 | 7,972 |
| Reference-contradicted correspondences | 1,609 | 9,007 |
| Unknown correspondences | 1,234 | 18,563 |
| Correct among judgeable matches | 32.6% | 47.0% |
| Judgeable coverage | 65.9% | 47.8% |

These counts use each method's own candidates and assignments. Unequal unknown coverage prevents treating the judgeable accuracy as accuracy across all reported matches. See the [direct evaluation guide](evaluation/src/tasks/reference_geometry/README.md).

## Sequential LDO optimization

The newer experiment trains on RetroOffice, selects on TinyHouse, and tests frozen
variants on six CountryHouse trajectories. Confidence-only filtering removes
32.5% of incorrect feature matches while retaining 96.6% of correct matches and
19/19 confirmed event hits. Candidate filtering removes 90.0% of false candidate
returns but reduces confirmed event hits to 17/19; it remains experimental.
Assignment-head training did not pass its development promotion check.

Use `ldo/configs/optimized-confidence.yaml` for the next confidence-only pilot.
See [all results and trade-offs](.docs/ldo-sequential-optimization-results.md) and
the [optimization task guide](evaluation/src/tasks/optimization/README.md).

## New environments: frozen confidence-only LDO

The [reference-depth v2 rescore](.docs/reference-depth-v2-results.md) subsequently
improved feature coverage to 74.4% for LDO and 26.4% for ORB, using official sky
masks and subpixel surface sampling. Model outputs and original results are
preserved. More evidence includes more incorrect matches: judged precision is
34.9% / 24.4%, respectively. Candidate/event labels retain the original policy.

On all 11 trajectories in AbandonedFactory2 and DesertGasStation (1,486 sampled
frames), LDO retrieved 48/53 confirmed reference events versus ORB's 42/53.
It returned 1,703 correct / 1,586 false candidate pairs versus ORB's 875 / 2,744,
with 3,470 / 3,140 unknown pairs, respectively. Judged feature precision improved
in both scenes, but many features remain unknown, particularly outdoors.
No model or evaluator thresholds were tuned on these environments.

See [results, coverage and limitations](.docs/ldo-unseen-tartanair-results.md) and
the [reproducible task](evaluation/src/tasks/unseen_tartanair/README.md).

## Matching optimization and fresh OldTownFall test

The next experiment compared ten pretrained matching configurations on 880
identical factory/desert development pairs. Only raising LightGlue confidence
from 0.3 to 0.4 passed the development promotion rules. Full-depth inference,
keypoint budgets, resolution changes and ALIKED were evaluated and retained in
the report, including failed promotions.

The frozen choice then ran on all three fresh OldTownFall trajectories:

| Measurement | Baseline LDO (0.3) | Selected LDO (0.4) |
| --- | ---: | ---: |
| Correct feature matches | 40,003 | 38,673 |
| Incorrect feature matches | 100,983 | 83,526 |
| Correct among judgeable features | 28.4% | 31.6% |
| Raw confirmed event hits | 17/17 | 17/17 |
| Events with >=20 correct correspondences | 13/17 | 12/17 |

This removes 17.3% of incorrect matches while retaining 96.7% of correct matches,
but loses one event under the external 20-correct-match diagnostic: one pair
drops from 20 to 19 correct matches. Keep 0.3 when event retention is the priority;
`ldo/configs/optimized-matching.yaml` remains a separate experimental option.
The diagnostic is not an accepted SLAM constraint or a runtime reference filter.

ORB + DBoW2 reached 11/17 raw events and 2/17 with the same usable-match diagnostic.
Its component correspondence baseline uses mutual Hamming ratio matching, rather
than the full ORB-SLAM3 acceptance pipeline. Feature counts use each method's own
retrievals; unknown reference evidence and unequal match density limit comparisons.

See [results and the lost-event diagnosis](.docs/ldo-matching-optimization-results.md),
the [predeclared plan](.docs/ldo-matching-optimization-plan.md), and the
[task guide](evaluation/src/tasks/matching_optimization/README.md). Factory/desert
data are development data for this newer selection. No fine-tuning was performed.

### Matching failure diagnosis

The [diagnostic task](evaluation/src/tasks/matching_diagnostics/README.md) now
explains the four baseline events below the 20-correct-match diagnostic. Three
have enough geometrically supported associations among the existing keypoints
(capacities 20, 37 and 46), but the model reports at most 7, 3 and 8 correct
matches. The fourth has capacity 2. Most rejected matches have large residuals.
The same assignment gap occurs in 67/352 positive development pairs.

These are reference-only diagnostic bounds, not recovered model results. Baseline
LDO remains at 13/17 usable events; numerical XYZ gates and original results are
unchanged. The next experiment should target association quality and low-overlap
observations. Future promotion must preserve every baseline usable event ID.
See [the full findings and visual examples](.docs/ldo-matching-diagnostics-results.md).

### Descriptor versus assignment analysis

The [descriptor audit](evaluation/src/tasks/descriptor_analysis/README.md) analyzed
all 352 positive development pairs. Of the 67 weak pairs, only 7 have enough
supported reciprocal top-1 descriptor associations, and 32 at top-5. Both
descriptor ambiguity and unused associations remain relevant. These are
reference-assisted capacities; no model improvement or promotion is claimed.
See [the numerical findings](.docs/ldo-descriptor-analysis-results.md).

### Joint image-pair matcher trial

The next fixed trial used official EfficientLoFTR on all 880 shared development
pairs. On validation it increased correct matches from 13,360 to 61,216 and
usable positive pairs from 104/128 to 117/128. Incorrect matches also increased
from 20,845 to 77,742, and judgeable coverage fell from 83.4% to 75.2%. It failed
the predeclared gates and was not promoted. No fresh test or full event replay
was run for this failed candidate. The baseline remains confidence 0.3.
See [results and limits](.docs/ldo-image-pair-matching-results.md) and the
[replaceable image-pair interface](evaluation/src/tasks/image_pair_matching/README.md).

## Earlier full-pipeline experiment: TartanAir V2

Seven ArchVizTinyHouseDay/Data_easy trajectories, identical grayscale images, K=5, and an equally applied 5-second temporal exclusion:

| Measurement | ORB + DBoW2 | LDO |
| --- | ---: | ---: |
| Candidate image pairs | 453 | 453 |
| Accepted constraints passing overlap and pose checks | 28 | 57 |
| Confirmed event runs reached by those constraints | 9/10 | 10/10 |
| Accepted constraints exceeding pose tolerance | 1/40 | 25/142 |
| Judgeable feature-match coverage | 65.9% | 47.8% |

LDO produced more independently confirmed constraints, alongside more accepted pose errors. A pose error does not by itself establish a false place detection. The shared geometric verifier estimates the transform from each method's observations. The pose tolerances are provisional: 0.20 m and 5 degrees.

This is a short synthetic pilot. Trajectories last 9-15 seconds; unknown reference labels withhold overall recall. Neither current detector consumes IMU, and the experiment does not establish long-term revisit performance, real-world superiority or out-of-distribution generalization.

- [Detailed findings and limitations](.docs/tartanair-reference-geometry-results.md)
- [Full pilot report](.docs/tartanair-pilot-report.md)
- [Frozen evaluation protocol](.docs/tartanair-reference-geometry-plan.md)

## Layout

```text
ldo/                         Replaceable detector components and model installation
loop_verification/           Shared observation-only geometric verifier
stereo_observations/          Stereo association and reconstruction
evaluation/                 Evaluation entry points, adapters and task modules
  src/tasks/feature_matching/ External feature XYZ evaluation and review GUI
  src/tasks/loop_closure/     Retrieval, independent event and pose assessment
  src/tasks/reference_geometry/ TartanAir reference-depth pilot
  src/tasks/unseen_tartanair/ Frozen comparison on new TartanAir environments
  src/tasks/matching_optimization/ Shared-pair matching ablations and fresh test
  src/tasks/matching_diagnostics/ Saved-evidence failure analysis and oracle bounds
  src/tasks/descriptor_analysis/ Descriptor rank and assignment opportunity audit
  src/tasks/image_pair_matching/ Frozen trial of a joint image-pair matcher
.docs/                       Architecture plans, research and findings
tests/                       Project tests
```

## Python environment

Python 3.11 and uv:

```powershell
uv sync --locked
uv run python -m pytest -q
```

GPU model inference and native ORB builds use WSL Ubuntu-24.04. Their environment and artifact paths are explicit in configuration; they must be installed separately on another machine. See [LDO installation](ldo/README.md), [shared verification](loop_verification/README.md), and the [TartanAir task guide](evaluation/src/tasks/reference_geometry/README.md).

## TartanAir task

After installing the model and native benchmark dependencies:

```powershell
uv run python evaluation/reference_geometry.py install
uv run python evaluation/reference_geometry.py prepare
uv run python evaluation/reference_geometry.py run --prepared evaluation/output/tartanair_reference_<id>
```

The installer pins dataset revision and verifies archive hashes. Saved runs include actual assignments, feature verdicts, verifier decisions, reference assessments and provenance. The FIFO evaluation file handler publishes dated Markdown and JSON reports.

Downloaded datasets, generated reference universes, raw run output, model checkpoints and virtual environments remain local. The repository contains source, configurations, the dependency lock and curated findings. Existing documentation may include local artifact paths from earlier experiments.
