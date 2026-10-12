# Image-pair matching trial: results

Completed 2026-10-10. The official EfficientLoFTR full FP32 adapter ran on all
880 original Factory/Desert development pairs. TartanAir supplies ground-truth
depth maps and poses. Retrieval/pair population and external XYZ rules stayed fixed.

**The candidate was not promoted.** It produced more correct matches and made
more positive pairs usable, but also returned substantially more incorrect matches
and reduced the fraction the evaluator could judge. Both fit and validation gates
failed. The research baseline remains SuperPoint + LightGlue at confidence 0.3.

## Validation: 320 identical pairs

| Measurement | Baseline SuperPoint + LightGlue | EfficientLoFTR trial |
| --- | ---: | ---: |
| Correct feature matches | 13,360 | 61,216 |
| Incorrect feature matches | 20,845 | 77,742 |
| Unknown feature matches | 6,801 | 45,861 |
| Correct among judgeable matches | 39.1% | 44.1% |
| Judgeable coverage | 83.4% | 75.2% |
| Positive pairs with ≥20 correct matches | 104/128 | 117/128 |

The trial returns 4.5 times as many matches overall. Correct matches rise 4.6×,
but incorrect matches also rise 3.7×. Unknown matches remain unknown; they are not
counted as incorrect. A 5 percentage point gain in judged precision does not meet
our requirement to reduce incorrect correspondence volume and preserve coverage.

For individual positive-pair identities, 103/104 baseline usable pairs remain
usable, one is lost and 14 newly become usable. These are image-pair diagnostics,
not accepted loop constraints or uniquely distinct revisit events.

## Fit: 560 identical pairs

| Measurement | Baseline SuperPoint + LightGlue | EfficientLoFTR trial |
| --- | ---: | ---: |
| Correct feature matches | 28,748 | 123,581 |
| Incorrect feature matches | 44,145 | 160,361 |
| Unknown feature matches | 16,600 | 79,768 |
| Correct among judgeable matches | 39.4% | 43.5% |
| Judgeable coverage | 81.5% | 78.1% |
| Positive pairs with ≥20 correct matches | 181/224 | 197/224 |

180/181 baseline usable positive pairs are retained, one is lost and 17 newly
become usable. Results are reported even though the fit gate failed; no threshold
or budget was retuned after inspecting validation.

## Where the trade-off appears

On reference-positive validation pairs, judged feature precision improves from
51.6% to 63.4%. On reference-negative validation pairs it falls from 5.4% to 3.7%;
incorrect matches increase from 5,506 to 26,706. The model is more productive on
genuine overlap but emits a large volume of unsupported associations elsewhere.
Pair overlap labels and feature verdicts remain separate measurements: these
numbers are not false accepted-loop rates.

This supports testing stronger joint matching, while showing that this pretrained
configuration's match selection is insufficient for our objective. It does not
prove which internal attention or descriptor operation causes each failure.
The upstream outdoor training domain may matter, but this experiment did not
isolate domain shift as a cause.

## Gates and resulting state

Both splits pass correct-match retention, usable-positive-pair retention and
nondecreasing judged precision per scene and overall. Both fail:

- Judgeable coverage preservation, in each scene and overall.
- Fewer incorrect matches overall.

Therefore no full chronological event replay or fresh dataset test was run for
this candidate, and it is not connected to the production Detector registry.
Those stages are conditional on preliminary eligibility in the predeclared plan.
The original OldTownFall baseline result remains 13/17 under its external
usable-event diagnostic. No model improvement is claimed for the active baseline.

## Implemented interface

`ldo.matching.image_pairs.ImagePairMatcher.match_images(query, history)` returns
actual subpixel coordinate pairs and scores through `PixelCorrespondences`.
`EfficientLoFTRMatcher` implements that seam with the pinned official source and
tensor-only checkpoint. Pair-dependent points do not use cached SuperPoint IDs.

The trial uses native grayscale 640×640 frames, full FP32, official coarse
threshold 0.2, output confidence >0.2, exact endpoint uniqueness and a maximum
of 1,024 confidence-ranked matches. No RANSAC or reference filtering enters it.

## Verification and provenance

- Full baseline-environment suite: **222 passed, 19 subtests passed**.
- New image-pair selection/gating tests: **6 passed**.
- Targeted Ruff checks and formatting passed.
- All **880 original baseline pair verdicts** reproduced exactly in the isolated
  candidate runtime before comparison.
- Original model/evaluator source, pair manifests, assignment evidence and
  reference semantics hashes verified.
- Official model source, checkpoint, converted tensor weights and runtime
  versions recorded and verified. Original baseline environment preserved.
- Timestamped JSON and Markdown published by the existing singleton FIFO handler.

Official source: [EfficientLoFTR](https://github.com/zju3dv/EfficientLoFTR), pinned
at `07e9c1401e71e9c556b1fda9d86d060af36ba176`. Research evaluation follows the
license bundled with that revision. Its pretrained model uses MegaDepth; there
is no new fine-tuning or audited out-of-distribution guarantee here.

- [Generated detailed report](ldo-image-pair-matching-report.md)
- [Machine-readable results and gating reasons](ldo-image-pair-matching-results.json)
- [Individual usable-pair retention audit](ldo-image-pair-matching-pair-retention.json)
- [Predeclared plan](ldo-image-pair-matching-plan.md)
- [Reproduction and interface guide](../evaluation/src/tasks/image_pair_matching/README.md)
- [Preceding descriptor diagnosis](ldo-descriptor-analysis-results.md)

Raw artifact root: `/opt/loop-detector/experiments/image_pair_matching/v1`.
