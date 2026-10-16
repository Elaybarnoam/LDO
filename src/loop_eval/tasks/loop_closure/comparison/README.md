# Independent LDO–ORB validation

The detector proposes image pairs and feature assignments. External stereo/XYZ evaluates those assignments. Independent loop reference labels evaluate candidate retrieval. Neither reference label nor ground truth enters a detector.

## Commands (project root)

```powershell
# Already prepared for MH_01; creation refuses to overwrite an existing reference.
uv run python evaluation/compare.py prepare

# Windows OpenCV, detector-blind original images. Requires reviewer and reason.
uv run python evaluation/compare.py review --reviewer Elay

# Reuse completed detector traces and external XYZ evidence.
uv run python evaluation/compare.py compare

# Fast retrieval-only refresh after reference annotation (no large XYZ reread).
uv run python evaluation/compare.py compare --retrieval-only

# Generate new assignments on the same independent pairs, then external XYZ.
uv run python evaluation/compare.py match --pair-limit 20

# Equal REQUESTED extraction cap: re-extract ORB and SuperPoint, then match.
uv run python evaluation/compare.py match --pair-limit 20 --feature-budget 1024

# Reanalyze completed fixed-pair results without inference.
uv run python evaluation/compare.py compare --fixed-checks evaluation/output/fixed_matching_RUNID

# Shared operational verification, supervised by the existing orchestrator.
uv run python evaluation/compare.py verify --supervised

# Five eligible queries for a short integration check.
uv run python evaluation/compare.py verify --query-limit 5

# Same verifier on completed fixed-pair matching outputs.
uv run python evaluation/compare.py verify --fixed-checks evaluation/output/fixed_matching_RUNID

# Combine one completed comparison JSON per sequence; duplicates are rejected.
uv run python evaluation/compare.py aggregate --reports REPORT1.json REPORT2.json
```

On Windows, analysis/inference forwards automatically to the installed Ubuntu-24.04 LDO environment. Reference review stays on Windows and reads native WSL images through its UNC share. Linux runs directly. Use `--config configs/evaluation/loop_closure/config.yaml` or a sequence-specific copy. Absolute path arguments should be separate values (`--config PATH`). Model paths and native installations in the configuration refer to WSL.

## Reference workflow

The default protocol selects every twentieth query before consulting detector predictions and enumerates all eligible histories with valid reference poses. It records missing-pose exclusions. Original images and reference inputs are hashed. Every label starts unknown. `pairs.jsonl` is immutable; review decisions append to `reviews.jsonl`, including reviewer, rationale and time. The latest explicit review wins, retaining earlier history.

OpenCV keys: L loop, N non-loop, U unknown, A/D previous/next, Q exit. Enter the rationale in the launching terminal. Shared physical scene is the criterion, not mere pose proximity. This is a reference annotation tool, not the existing feature viewer. Candidate scores, model identities and feature correspondences are hidden. Manual labels are reviewer judgments, not perfect ground truth; independently review ambiguous cases before publication.

Recall/query success require the entire selected query history to be decisively labeled. Incomplete queries do not enter their denominator. Precision bounds retain unknown returns. Labeled-subset precision is diagnostic only. Reported ranks are retained after missing-pose exclusions; no model receives a refill. Reference-complete query recall is conditional on that subset: always inspect its coverage before interpreting it.

## Matching controls

Fixed pairs are sampled by seeded hash of timestamps, not by either model's scores or XYZ outcomes. Normal mode uses the pinned native ORB exports and configured SuperPoint/LightGlue engine. Equal-cap mode runs the parity-verified native binary with a copied settings file changing only `ORBextractor.nFeatures`, and gives the same requested cap to SuperPoint. Actual counts may differ. Preserve each method's original preprocessing; this evaluates configurations, not identical feature input.

Temporal ORB correspondences use the existing mutual Hamming ratio matcher, not the full ORB-SLAM3 geometric acceptance pipeline. LDO matches come from its registered pair engine. No temporal RANSAC/grid verdict filter is introduced. Stereo disparity predictions are cached in one shared directory for both methods; the existing v8 numerical XYZ and v2 stereo preparation remain unchanged. Historical outputs are copied, never modified. Zero-match pairs stay in the fixed-pair comparison.

Final dated JSON/Markdown reports pass through the existing singleton FIFO writer. They archive the protocol, reference universe/review journal and comparison source. Per-query counts, paired temporal-block intervals, hashes, matching controls, feature micro totals, per-pair macro metrics and unknown coverage remain available in JSON. Bootstrap precision/recall intervals are for reference-complete queries, not all unknown candidates. At least two usable temporal blocks are required; a within-sequence interval does not prove generalization.

## Held-out runs and claim boundary

MH_01 is development. Install and run held-out V1_01/V2_01 with the existing dataset installer and benchmark orchestrator, making sequence-specific copies of their configs and this comparison config. Freeze protocol/model settings before examining test results. Prepare/review an independent reference for each, then aggregate one report per sequence. The aggregator withholds an equal-sequence mean if any included sequence lacks that metric; it never silently drops unavailable sequences.

No command automatically declares LDO superior. Independent labels, held-out evidence, uncertainty and training-data overlap audit are required. Four-pair smoke results and raw supported-feature totals are not proof of more correct loop closures. Equal-precision operating-point sweeps remain a later experiment after labels exist; choose thresholds on development data, not test labels.

## Shared operational verification

Both adapters provide their own feature assignments to one query-stereo-depth PnP/RANSAC verifier. It refines the metric relative pose, recomputes inliers and applies identical count, ratio, residual, cheirality and conditioning gates. It does not read reference poses or XYZ verdicts. ORB assignments remain mutual Hamming matches from the pinned extractor; this is not native full ORB-SLAM3 loop acceptance.

`--verifier-config`, `--stereo-config` and `--assessment-config` select separate policies. Defaults are provisional development settings. The evaluation adapter computes pose error only after verification. An accurate pose with an unknown loop label is unresolved, not a confirmed loop. Reported median pose errors cover all available estimates, including rejected estimates. Missing reference poses exclude a pair from evaluation. Missing stereo depth yields insufficient evidence.

The supervisor owns lifecycle, cancellation and exit checks. The benchmark publishes `loop_candidate_verified` events and a final `comparison_result`; the singleton FIFO handler owns report writing. Artifact JSONL retains assignment IDs, residuals, estimated transforms, assessment and reason codes. Fixed-pair experiments withhold detector recall. Sequence aggregation requires the same operational and assessment policies and does not mix verified reports with retrieval-only reports.

## Primary feature evaluation and secondary verification audit

```powershell
uv run python evaluation/compare.py audit --verification-report evaluation/output/evaluation_RUN.json
```

This read-only command joins a completed operational report to all saved external XYZ evidence for both methods. It verifies saved file hashes, numerical XYZ policy parity, pair identity, image hashes and reported match counts; incompatible evidence is an error. It produces a dated report through the existing singleton FIFO handler. No model inference or threshold change is performed.

The primary totals always include accepted, rejected and insufficient-evidence candidates. The secondary tables group those same feature verdicts by operational outcome. Pair-level JSON includes rejection reasons, pose assessment and verifier diagnostics. The Markdown lists rejected candidates with strong XYZ support.

Strong support is only a descriptive highlight: at least 8 XYZ-supported matches, at least 80% support among judgeable matches, and at least 40% evaluation coverage. This policy is saved in the report and changes neither XYZ nor operational acceptance. All pairs remain in JSON. Supported features alone are not independent loop labels. Use disagreement cases to investigate estimator failures and select operational thresholds on development data; do not automatically relabel them or tune against held-out results.
