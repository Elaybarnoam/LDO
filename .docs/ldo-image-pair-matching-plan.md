# Targeted image-pair matching experiment

## Motivation and scope

The descriptor audit found only 7/67 weak positive development pairs have enough
supported reciprocal top-1 descriptor associations, versus 32/67 at top-5. Test
one image-pair-conditioned engine, EfficientLoFTR, without changing MegaLoc or
the external depth-v2/XYZ reference rules. Use only provided TartanAir depth maps
and poses. OldTownFall is excluded from selection and from fresh-test claims.

The [official implementation](https://github.com/zju3dv/EfficientLoFTR) accepts
two grayscale images and returns subpixel matches. Its pretrained outdoor model
may have an indoor domain gap; the experiment must establish suitability locally.

## Frozen candidate, before any accuracy results

- Official repository revision `07e9c1401e71e9c556b1fda9d86d060af36ba176`.
- Official `eloftr_outdoor.ckpt` linked by the repository; record download checksum.
- Full configuration, FP32, native 640×640 grayscale images, no resizing.
- Official coarse threshold 0.2; output confidence must exceed 0.2.
- Return at most 1,024 confidence-ranked matches; remove exact duplicate endpoints.
- No ground-truth filtering, RANSAC, fitted reference pose or parameter search.
- Image-pair interface returns actual pixel coordinates and scores. Pair-dependent
  points must not be represented as cached SuperPoint feature IDs.

## Evaluation order

1. Freeze model provenance, configuration, source and the original pair manifest.
2. Run the identical 880 fixed development pairs, preserving zero-output pairs:
   560 fit and 320 validation, including positive, negative and unknown labels.
3. Recompute every original baseline match verdict in the candidate environment
   and require exact equality with saved verdicts before comparing models.
4. Report correct / incorrect / unknown matches and ≥20-correct positive-pair
   diagnostics per scene and split. Reference geometry never enters the model.
5. Require ≥90% correct-match retention, ≥95% usable-positive-pair retention,
   nondecreasing judged precision and judgeable coverage per scene and overall,
   plus fewer incorrect matches overall on both splits.
6. If either split fails, keep the baseline and report the failed trial. Do not
   retune on validation or run a fresh test for a failed candidate.
7. If both pass, proceed to full chronological development replay and require
   preservation of every baseline usable event ID using the existing guard.
   Freeze a passing choice before another untouched environment test.

Passing shared pairs is preliminary eligibility, not production promotion.
No result of this experiment alone proves real SLAM loop acceptance or trajectory
improvement. All reports go through the existing FIFO evaluation file handler.

## Runtime isolation

Use `/opt/loop-detector/efficientloftr-env`, with explicit access to the existing
Torch installation and its own pinned inference dependencies. Keep the original
baseline environment unchanged. Save runtime versions, model/source hashes and
the upstream license. No company/project registration or messages are submitted;
this trial is research evaluation under the upstream license's research clause.
