# LDO descriptor and assignment analysis: findings

Completed 2026-10-10 on all 352 frozen positive Factory/Desert development pairs.
TartanAir provides the ground-truth depth maps and poses. The current matching
model, retrieval, XYZ evaluator and original assignments remain unchanged.

## Main finding

The gap is mixed: many compatible alternatives are weakly ranked by the current
descriptors, while some strongly ranked alternatives are also missed by the
contextual matcher. The evidence does not justify attributing everything to
LightGlue or replacing it with raw nearest-neighbour matching.

Among the 67 baseline pairs below the existing 20-correct-match diagnostic:

| Supported one-to-one capacity restriction | Fit (43 weak pairs) | Validation (24 weak pairs) | Combined |
| --- | ---: | ---: | ---: |
| No descriptor-rank restriction | 43 | 24 | 67 |
| Reciprocal descriptor top-1 | 6 | 1 | 7 |
| Reciprocal descriptor top-5 | 23 | 9 | 32 |
| Reciprocal descriptor top-10 | 25 | 13 | 38 |
| Reciprocal descriptor top-50 | 34 | 21 | 55 |

These are reference-assisted capacities, not recovered matches. Reciprocal means
the same edge ranks within the budget in both images. One-to-one maximum matching
prevents reusing a feature to inflate the counts.

## Descriptor ambiguity and unused opportunities

Across all 352 selected positive pairs, 13,257 query keypoints have a supported
alternative but no supported baseline assignment:

- 2,841 (21.4%) have a forward top-1 supported alternative.
- 6,265 (47.3%) have a forward top-5 supported alternative.
- 7,633 (57.6%) have a forward top-10 supported alternative.

Forward rank alone does not imply reciprocal uniqueness. The rest require wider
descriptor search even before contextual matching is considered. Raw SuperPoint
cosine similarity is not LightGlue's learned internal score, so these numbers do
not establish a specific internal assignment bug.

Among 35,928 contradicted baseline assignments on these positive pairs, only 561
have a higher-cosine supported alternative for the same query keypoint. A raw
similarity swap therefore has limited demonstrated scope for correcting the
observed contradictions.

## Current usable-pair diagnostic

| Split | Baseline pairs with ≥20 correct matches | Reference-supported reciprocal top-1 capacity ≥20 |
| --- | ---: | ---: |
| Fit (224 positive pairs) | 181 | 179 |
| Validation (128 positive pairs) | 104 | 93 |

This demonstrates why descriptor nearest-neighbour matching is not an adequate
replacement by itself. Geometry-assisted rank counts already fall below the
baseline in validation. They do not measure a deployable matcher's complete
correct/incorrect/unknown output or event coverage.

## Next targeted experiment

Test one image-pair-conditioned matching engine that can jointly locate and
associate points in the shared image content, against the frozen sparse baseline.
The diagnostic motivates this broader seam because both descriptor ranking and
feature availability can limit the current pipeline. It does not guarantee that
such an engine will improve results.

Keep MegaLoc retrieval and reference-depth/XYZ rules fixed. First compare the
same development pairs, including negatives and unknowns. If those gates pass,
run full chronological development replays with baseline event-ID preservation,
then freeze before testing another untouched environment. OldTownFall is now
post-test explanation data and cannot be reused as fresh validation.

## Verification and artifacts

- Full WSL suite: **216 passed, 19 subtests passed**.
- Targeted descriptor/geometry tests: **14 passed**.
- Targeted Ruff checks and formatting passed.
- Frozen original source hashes and per-pair geometry/assignment hashes verified.
- Cached descriptor and input image hashes verified; keypoint arrays aligned with
  saved geometry and assignment indices.
- Original one-to-one geometric capacity reproduced for every pair.
- Reports published through the existing singleton FIFO evaluation handler.

No new matcher, training, promotion or fresh test is claimed. Baseline OldTownFall
performance remains 13/17 under the external usable-event diagnostic.

- [Generated detailed report](ldo-descriptor-analysis-report.md)
- [Machine-readable results](ldo-descriptor-analysis-results.json)
- [Plan](ldo-descriptor-analysis-plan.md)
- [Reproduction guide](../evaluation/src/tasks/descriptor_analysis/README.md)

Raw artifact root: `/opt/loop-detector/experiments/descriptor_analysis/v1`.
