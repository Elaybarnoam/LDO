# Independent revisit-event evaluation

This task establishes a detector-independent reference before measuring correct triggers and missed events. The main measurement is distinct continuous real revisits; pair correctness and query success are supporting measurements. External XYZ and operational pose verification remain separate.

## Commands from the project root

The new commands default to `configs/evaluation/loop_closure/revisit_config.yaml`, which includes all replay queries. Use a separate config for another sequence.

```powershell
# Refuses to overwrite existing reference directories.
uv run python evaluation/compare.py revisits-prepare

# Native Windows OpenCV: original query/history images, neighboring context.
uv run python evaluation/compare.py revisits-review --reviewer REVIEWER_ID

# Optional import of independent interval decisions (JSONL), validated first.
uv run python evaluation/compare.py revisits-import --decisions reviewed_intervals.jsonl

# New immutable snapshot, retaining the append-only live journal.
uv run python evaluation/compare.py revisits-freeze --snapshot-output evaluation/references/MH_01_easy_revisits_v1/snapshots/SNAPSHOT_ID

# Equal K evaluation; optional completed full verifier/audit report for secondary evidence.
uv run python evaluation/compare.py revisits-evaluate --frozen-reference SNAPSHOT_PATH --verification-report VERIFICATION_REPORT.json

# Development score sweeps at the declared target precision, never using incomplete truth.
uv run python evaluation/compare.py revisits-select --frozen-reference SNAPSHOT_PATH

# Apply frozen development points to a separately reviewed held-out sequence.
uv run python evaluation/compare.py revisits-evaluate --config HELD_OUT_CONFIG.yaml --frozen-reference HELD_OUT_SNAPSHOT --operating-points OPERATING_POINTS.json

uv run python evaluation/compare.py revisits-aggregate --reports SEQUENCE1.json SEQUENCE2.json
```

`prepare` is performed once. The existing MH_01 reference is already prepared. Subsequent annotation, freezing and evaluation can be repeated with new snapshot/report IDs. Windows inference/analysis forwards to WSL; review stays on Windows. Source and frozen-reference artifacts are archived by the existing singleton FIFO report writer.

## Reference rules

- Every temporal/pose-admitted pair stays in the universe, including pairs neither detector returned.
- Distance/orientation gates only prioritize review. Outside-proposal pairs are not automatic negatives.
- Labels concern shared identifiable static physical scene; position proximity alone is insufficient.
- The GUI hides detector predictions, feature matches, prior reviewer labels and operational verdicts.
- A decision needs reviewer, reason, timezone-aware time and detector-blind declaration.
- Interval decisions cover only explicitly reviewed query/history rectangles. Use a single pair or smaller rectangle if overlap cannot be established across the full range.
- Positives and pose-proposed or visually flagged hard negatives need two different reviewers agreeing. Other negatives need one. Disagreements and explicit uncertainty remain unknown until reviewers revise their decisions.

GUI: L/N/U for loop/non-loop/unknown; A/D previous/next pair; W/S query frame; J/K history frame; G jump to two timestamps; Q quit. The terminal accepts optional `q_start q_end h_start h_end` bounds (blank means the center pair), then a justification and optional hard-negative flag for visually repeated scenes. Proposals are shown first; all other eligible pairs remain reachable. Neighboring original frames supply context. Reviewer identity does not imply permission to consult detector evidence during reference labeling.

## Event and metric rules

Positive query runs become one continuous event regardless of how many historical returns they permit. Negative/unknown queries break runs; the frozen maximum-gap policy also splits events. One correct return detects the event. First-detection delay and sustained successful queries remain diagnostics. Known events missed by both methods stay in the denominator.

Overall event recall is unavailable for an incomplete reference. Known-event recall is explicitly diagnostic. Pair precision is unavailable if any evaluated return is unknown; bounds retain them. Original ranks are never refilled after exclusions or thresholds.

Score sweeps are computed efficiently by sorting scored returns and incrementally tracking pair/event hits. Operating points meet the same declared target precision; achieved precisions are saved and may differ. Threshold/model/policy fingerprints are frozen and checked during held-out evaluation. Selection requires complete development truth. Applying an unavailable operating-point artifact or evaluating development data as held-out raises an error.

## Current real run

MH_01 reference: 52,326 eligible pairs; 363 pose-admitted query frames; 323 query frames with eligible history; 6 queries excluded for missing reference poses. Pose aids propose 10,769 pairs in two query intervals. These are not two confirmed loop events.

No independent scene decisions have yet been supplied. The initial frozen snapshot is explicitly unreviewed. Consequently confirmed-loop precision, overall event recall and development threshold selection are unavailable. Existing secondary geometric and unfiltered XYZ results remain visible. This is an honest completed software run, not completed scientific validation.
