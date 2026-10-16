# LDO matching optimization: fixed-pair experiment

Declared before running variants, 2026-10-10. Original model configurations and
independent XYZ evaluators remain available. No dedicated transformer training
is included; the seven agreed steps concern pretrained inference and extraction.

## Data roles

Already inspected AbandonedFactory2 and DesertGasStation are now development
data, not unseen evidence for a newly selected model. Fit: factory P000–P003,
desert P000–P002. Validation: factory P004–P005, desert P003–P004. These are
trajectory-disjoint but share environments. OldTownFall/Data_easy is the fresh
test environment; use all installed trajectories and do not select on outcomes.
Pretrained dataset exposure is unaudited.

Freeze up to 32 reference-positive, 32 reference-negative and 16 unknown image
pairs per development trajectory, deterministically ordered by SHA256(seed,
scene, trajectory, timestamps). Prefer the existing ORB/LDO retrieval union;
this includes hard retrieval negatives. The identical pair list is used by every
matcher, including ORB. Keep zero-match pairs in all denominators.

## Steps and promotion rule

1. Baseline: pretrained SuperPoint (1024 points, native resolution) + adaptive
   LightGlue, confidence 0.3. Record ORB on the same pairs.
2. Sweep match confidence 0.3, 0.4, 0.5, 0.6. Scores can be filtered from identical
   assignments because the upstream threshold is applied after assignment.
3. Compare adaptive with full-depth/no-pruning LightGlue at fixed extraction.
4. Test 512/1024/2048 keypoints at fixed resolution, then longest-side resolution
   480/native-640/960 at the selected point count. Resizing must preserve original
   pixel coordinates and image sizes for matching and external evaluation.
5. Compare ALIKED-n16 + its compatible LightGlue checkpoint, with the same point
   budget, resize setting and inference mode. Fingerprint extractor/checkpoint
   changes; do not mix descriptors or adapted SuperPoint heads with ALIKED.
6. Promote a fit-selected candidate only if validation passes the same gates.
   For every development scene and overall: retain >=90% baseline correct matches,
   >=95% baseline usable positive pairs, do not lower conditional precision, and
   reduce incorrect matches overall. A usable pair has >=20 independently correct
   correspondences; this is an evaluation proxy, not a runtime ground-truth gate
   or an accepted SLAM loop. Compare cumulative retention to the original baseline,
   preventing repeated small losses from bypassing the floor.
7. Freeze the final configuration before test inference. Run original ORB and
   baseline/selected LDO end to end on all OldTownFall trajectories, using identical
   images, approximately 2 Hz, K=5 and five-second exclusion. Report raw retrieval
   separately from events reached by pairs with >=20 correct correspondences.

All candidates and failed promotions are reported. The selection objective is
fewest incorrect matches subject to retention/precision gates, then more correct
matches, then deterministic configuration ID. If no candidate passes, retain the
baseline. Unknown evidence is not negative supervision.

## Evaluation and artifacts

Use frozen reference-depth v2 for individual features (official sky masks, active
inverse-depth sampling, unchanged XYZ/reprojection tolerances). Existing pair
labels retain their original overlap policy. Reference data never enters the
extractor, matcher, retrieval or runtime acceptance policy. No RANSAC selection.

Persist dataset/replay/pair-list hashes, model artifact manifests, actual scores,
indices and independent verdicts for each run, per-scene and per-trajectory counts,
code/config snapshots, step decisions and dated Markdown/JSON reports through the
shared FIFO writer. Timing is recorded but is not a promotion objective.
Keep the original baseline config and produce a separate selected config.

Validate production adapters with empty inputs, incompatible families, resizing
coordinate round trips, cumulative promotion gates, zero-match denominators,
deterministic shared-pair selection, asset integrity, and actual GPU smoke runs.
Fine-tuning is a subsequent experiment if the pretrained changes do not suffice.
