# LDO sequential optimization experiment

Test environment: **CountryHouse**; 6 trajectories.

Training: RetroOffice. Development: ArchVizTinyHouseDay. All choices frozen before CountryHouse model evaluation; no test-driven tuning.

## Held-out results

Correct/incorrect below refer to individual feature correspondences under the unchanged reference-depth/pose gates. Unknown is not incorrect.

| Variant | Correct feature matches | Incorrect feature matches | Unknown | Correct among judgeable |
| --- | ---: | ---: | ---: | ---: |
| ORB + DBoW2 | 14161 | 7856 | 2123 | 64.3% |
| baseline | 146270 | 66687 | 53618 | 68.7% |
| confidence | 141287 | 45003 | 39409 | 75.8% |
| candidate_policy | 134984 | 33794 | 34916 | 80.0% |
| full_depth_control | 138131 | 35737 | 37052 | 79.4% |
| adapted_head | 137940 | 35431 | 36731 | 79.6% |

### Candidate image pairs and confirmed revisit events

A correct candidate satisfies the frozen 20% bidirectional visible-overlap rule. These counts are separate from individual feature correctness and from pose accuracy.

| Variant | Correct candidate pairs | False candidate pairs | Unknown pairs | Confirmed event hits |
| --- | ---: | ---: | ---: | --- |
| ORB + DBoW2 | 497 | 1011 | 71 | 19/19 |
| baseline | 670 | 791 | 118 | 19/19 |
| confidence | 670 | 791 | 118 | 19/19 |
| candidate_policy | 633 | 79 | 88 | 17/19 |
| full_depth_control | 638 | 88 | 90 | 18/19 |
| adapted_head | 636 | 86 | 89 | 18/19 |

### Reference coverage and unknown bounds

| Variant | Judgeable matches | Correct fraction bounds over all reported matches |
| --- | ---: | --- |
| ORB + DBoW2 | 91.2% | 58.7%–67.5% |
| baseline | 79.9% | 54.9%–75.0% |
| confidence | 82.5% | 62.6%–80.1% |
| candidate_policy | 82.9% | 66.3%–83.4% |
| full_depth_control | 82.4% | 65.5%–83.1% |
| adapted_head | 82.5% | 65.7%–83.1% |

## Each change against its predecessor

| Step | Correct matches retained | Incorrect matches removed | True candidates retained | False candidates removed | Confirmed event hits retained |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 96.6% | 21684 | 100.0% | 0 | 100.0% |
| 2 | 95.5% | 11209 | 94.5% | 712 | 89.5% |
| 3 | 102.2% | -1637 | 100.5% | -7 | 105.9% |
| learning_vs_equal_compute | 99.9% | 306 | 99.7% | 2 | 100.0% |
| overall | 92.3% | 32893 | 94.5% | 712 | 89.5% |

Negative removals mean more errors. Retention above 100% means more correct matches or candidates. Event hits are over confirmed reference events, not overall recall with unknown labels.

## Interpretation

Confidence filtering retained 96.6% of correct feature matches and removed 21684 incorrect matches.

Candidate filtering retained 94.5% of known correct candidates and 89.5% of confirmed event hits. The predeclared event-retention floor is 90%.

Candidate filtering failed that event-retention floor on this held-out environment; keep it experimental and prefer confidence-only for this pilot. No parameters were retuned on these test results.

## Fine-tuning decision

Adapted head promoted on development: **False**. The full-depth pretrained control separates learning from a change in inference computation.

## Limits

ORB is the original unfiltered K=5 baseline. The LDO candidate policy can abstain, so fewer false returns alone do not establish superiority over a similarly calibrated ORB detector. Compare retained true candidates and event hits alongside errors.

- One held-out synthetic environment; upstream pretraining overlap unaudited.
- Unknown reference matches remain unknown, not incorrect.
- Candidate labels use frozen 20% bidirectional visible overlap; not pose accuracy.
- No latency or real-world SLAM improvement claim from this experiment.

Baseline evidence: `/mnt/c/Users/elayb/OneDrive/Documents/visual–IMU loop detector/evaluation/output/comparison_2026-10-09_18-40-31_408161_319882d6.json`

Freeze manifest SHA256: `f21980432b297b11939bae259b2dc810ca37d5a2bfd330291bd8a0d0c44a5495`
