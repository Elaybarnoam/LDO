# Independent revisit evaluation plan

Date: 2026-10-07. Decisions: user accepted all recommendations from the interview, including the remaining review, uncertainty and reporting rules below.

## Claim and measurement ownership

Main outcome: distinct real revisit events detected at controlled false-positive rates. Supporting outcomes: correct candidate pairs, per-query success and reported feature correctness. Twenty consecutive returned pairs from one continuous revisit are not twenty distinct events.

A positive reference means that the original camera observations share identifiable static physical scene with useful visual overlap. Nearby poses alone are insufficient; repeated structures at different physical locations are negatives when independently established. Ambiguity remains unknown.

The independent reference owns truth. ORB/LDO propose pairs; the shared operational verifier evaluates an estimated connection; external XYZ evaluates reported correspondences unchanged. Ground truth is absent from the operational APIs.

## End-to-end topology

```text
Chronological replay + ground-truth camera poses
  ? full eligible query/history universe (including never-returned pairs)
  ? pose-assisted revisit proposals (review aids only)
  ? detector-blind original-image/context review
  ? append-only interval/pair decisions + independent second review
  ? immutable frozen reference + continuous revisit events
  ? validated ORB/LDO traces under the same history/exclusion/K
  ? pair precision + query success + distinct-event recall
  ? optional secondary operational-pose results and external XYZ report
  ? development threshold selection ? frozen operating points
  ? held-out evaluation ? dated FIFO JSON/Markdown reports
```

## 1. Reference universe and proposals

Create a new reference directory; preserve the old stride-20 reference and all historical evidence. Include every replay query with a valid reference pose, every eligible earlier frame with a valid reference pose, and the existing 20-second temporal exclusion. Use query stride 1 for event evaluation.

Generate pose-distance/orientation review proposals without reading detector predictions or XYZ results. Initial development proposal distances are 3 m and 90 degrees; these are broad workload aids, not correctness thresholds. Every other eligible pair stays unknown and available for review. Proposal misses must never become automatic negative labels. Save input hashes and the proposal policy.

## 2. Independent annotation and quality

Review original images plus neighboring-frame context with detector identity, scores, feature assignments and verifier results hidden. Record reviewer identity, reason, UTC time and reviewed timestamp ranges. Interval decisions apply only to explicitly reviewed query/history rectangles; the reviewer must affirm the shared-scene judgment across the whole rectangle. Narrow a rectangle or mark unknown if that cannot be established.

Positives and pose-proposed or independently visually flagged hard negatives require agreement from two distinct reviewers before becoming decisive. Ordinary negatives require one review. Disagreements remain unknown pending explicit re-review. A later revision preserves all earlier decisions. Never manufacture manual labels from pose gates or either model's output.

## 3. Events, unknowns and missed opportunities

A revisit event is a continuous run of query frames with independently confirmed positive associations. Merge multiple historical matches for the same query into one opportunity. Split when the positive run is interrupted, including unreviewed queries; unknown segments never bridge events. A development maximum consecutive-query gap of 1.5 seconds handles sparse/missing replay observations. Save this policy before comparisons.

One independently correct returned pair during an event counts as event detection. Sustained detections, first-detection delay and usable pose estimates are separate diagnostics. An event missed by both methods remains in the denominator. Compute known-event diagnostics even for partially labeled references, but withhold overall event recall when the reference universe is incomplete. Report known events and remaining unknown coverage prominently; bounds must not invent event counts for unknown regions.

## 4. Candidate and connection metrics

For equal candidate budgets K=1 and K=5, report TP/FP/unknown returned pairs, precision/bounds, query success and event detection. Do not refill ranks after missing-pose exclusions or score thresholds. Repeated observations are not unique landmarks.

Compute a matched-precision operating-point comparison from independently labeled development data. Sweep each method's own retrieval score thresholds; higher score means more similar for both saved adapters. Threshold selection uses only reference-complete development data and a declared target precision. Freeze thresholds, configuration/source/trace/reference hashes and development sequence identity. If labels are incomplete or no point satisfies the target, report unavailable rather than choosing an optimistic point.

Accepted geometric connections are a secondary outcome: independent positive pair plus an estimated pose satisfying the frozen assessment policy. External XYZ retains all reported matches, including rejected candidates. Its formulas and thresholds remain unchanged.

## 5. Development and held-out controls

MH_01 is development because it has already informed debugging and settings. Reserve V1_01 and V2_01 for held-out evaluation. Freeze protocol, model, verifier and chosen score thresholds before examining held-out results. Reusing a held-out sequence to tune settings makes it development evidence for the new version. Training-data overlap remains an explicit audit requirement.

Freeze each annotation snapshot; ongoing journals cannot change the denominator of an already published run. Reports archive the snapshot and source policy. Held-out evaluation rejects operating points selected on that same sequence and settings/reference changes. Keep per-sequence results and equal-sequence aggregates; do not silently drop unavailable metrics. Use paired event/block uncertainty when at least two independent temporal blocks are available; otherwise withhold intervals.

## Implementation file tree

```text
evaluation/src/tasks/loop_closure/
  revisits/
    __init__.py
    policy.yaml                 # proposals, event boundaries and review quality
    reference.py                # prepare, journal consensus, freeze and hash validation
    review.py                   # blind interval/pair review with image context
    metrics.py                  # event, query and pair outcomes
    operating_points.py         # development selection and frozen held-out thresholds
    workflow.py                 # CLI adapter, report provenance and integration
  revisit_config.yaml           # full replay reference; shared detector traces
  comparison/cli.py             # thin command dispatch
```

Reuse the existing reference loader/trace validator and singleton FIFO report writer. Numerical XYZ and runtime verifier remain unchanged.

## Completion and evidence rules

Implement and test independent preparation, consensus/unknown handling, immutable freezing, event grouping, missed opportunities, threshold controls, blind review and dated reporting. Run the new full MH_01 workflow, inspect saved proposal/reference/trace counts and produce actual results.

A prepared or frozen all-unknown reference is a valid software artifact, not a finished scientific annotation. Report its actual review status. Independent reviewers must supply scene decisions before detector precision/recall or superiority can be established. The implementation must make that remaining work actionable without asking the user to approve routine development steps.

## Implementation completed and measured ? 2026-10-07

- [x] New full-replay reference without modifying historical stride-20 artifacts.
- [x] Detector-independent pose-assisted proposals, retaining all other pairs unknown.
- [x] Blind original-image/context review and validated interval imports.
- [x] Append-only reviewer consensus, explicit disagreement handling and hash-protected snapshots.
- [x] Distinct-event grouping, missed-opportunity denominators and pair/query diagnostics.
- [x] Shared-budget evaluation and development-only score selection with frozen held-out controls.
- [x] Secondary pose results, unchanged unfiltered XYZ evidence and FIFO dated reports.
- [x] Equal-sequence aggregation that preserves unavailable metrics.
- [x] Synthetic behavioral tests and real MH_01 preparation/evaluation/UI-render checks.
- [ ] Independent scene decisions from reviewers (not inferred from pose proposals).
- [ ] Labeled development calibration, frozen operating points and held-out scientific runs.

Actual preparation: 52,326 eligible pairs; 363 pose-admitted queries; 323 with eligible history; 10,769 pose-proposed pairs in 2 query intervals. All 52,326 reference labels remain unknown because no independent reviewers have supplied scene judgments. The initial snapshot is deliberately named `unreviewed_development_2026-10-07`.

At K=5, all 1,540 ORB and 1,512 LDO externally evaluated candidate pairs reconcile with the full reference. Pose-proposal diagnostics contain 805 ORB and 947 LDO returns inside the review aids; both reach both proposal intervals. These are not true-positive loop counts.

Secondary geometric acceptances remain ORB 454 and LDO 1,071; reference-accurate accepted estimates remain 423 and 929 under provisional tolerances. External XYZ formulas, thresholds and all-match totals remain unchanged. Loop precision, overall event recall and target-precision threshold selection are correctly unavailable until labels exist.

Validation: 135 tests passed, 1 skipped, 19 subtests passed; lint/format checks passed. The blind context panel rendered from real original images on Windows without creating annotation decisions. Software is implemented; independent truth and held-out claim validation remain explicit evidence work.
