# LDO matching failure diagnosis

## Objective

Explain why baseline confidence-0.3 LDO reaches all 17 confirmed OldTownFall
events in retrieval but only 13 with at least 20 independently correct matches.
The 20-match boundary is an evaluation diagnostic, not a SLAM acceptance rule.
Preserve all original inference, reference labels, numerical XYZ code and gates.

## Diagnostic sequence

1. Replay the saved assignments and reproduce the four missed events. Their best
   retrieved positive pairs have 0, 7, 3 and 8 correct matches.
2. Inspect every retrieved reference-positive pair belonging to those events.
   Verify image, feature, assignment, pose, depth and semantic evidence hashes.
3. Construct a reference-only graph between the *existing* query and historical
   keypoints. An edge exists only when the unchanged XYZ/reprojection evaluator
   supports that correspondence. Projected-point radius search generates a
   complete candidate set under the fixed forward reprojection bound. Maximum
   bipartite matching gives the largest possible one-to-one supported assignment.
4. Separate reported supports, contradictions, unknown evidence, nearby geometric
   failures and large residuals. A small residual alone does not prove physical
   feature identity or a localization defect. Low oracle capacity can reflect
   extraction, visibility, localization or reference limitations; do not assign
   a more specific cause without further evidence.
5. Report unused geometrically supported associations, valid-depth availability,
   projected visibility, residual distributions and the best capacity per event.
   This oracle is exclusively an evaluator; models must never receive its edges.
6. Use independent factory/desert development evidence to test any targeted
   production improvement justified by the diagnosis. Selection requires fewer
   incorrect matches and no loss of baseline usable events on fit and validation.
   Test candidate policies using image observations only.
7. Promote only after those gates pass. A promoted candidate requires a new fresh
   environment test, frozen before inference. A failed candidate is retained in
   the report and the baseline remains recommended.

OldTownFall is now available for post-test explanation. Its original result stays
immutable, and it cannot be reused as unseen validation of a fix inspired by this
analysis. Do not lower the evaluator threshold to recover an event.

## Implementation boundaries

Use a new `evaluation/src/tasks/matching_diagnostics/` task. Keep frozen matching
optimization sources intact. Pure geometry-analysis functions are independent
of model loading. Report via the existing FIFO evaluation file handler; persist
direct JSON, per-pair NPZ and provenance in a dedicated artifact root. Include
tests for maximum matching, invalid reference evidence, unused correct edges,
and geometric failures that must not be relabelled as supports.
