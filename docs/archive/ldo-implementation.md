# LDO first configuration: implementation and verification

2026-10-04 update: stereo preparation now recovers cropped raw-image observations and reports coverage by image domain. The numerical XYZ calculation and thresholds remain unchanged. See [the coverage investigation and corrected replay](stereo-coverage-investigation.md). The results below record the original 2026-10-03 implementation run.

Date: 2026-10-03. Implemented: standalone `LDO-MegaLoc-LightGlue` inference, benchmark integration, existing stereo + XYZ evaluation, timestamped reports and feature review. Native SLAM map correction and training are subsequent work.

## What is implemented

- Typed model interfaces, frozen feature/correspondence dataclasses and configuration-selected adapter factories.
- Pretrained MegaLoc descriptors and exact normalized cosine search over eligible history.
- SuperPoint original-pixel observations and compatible pretrained LightGlue assignments.
- Query-before-insert chronology, timestamp/ID/session checks and explicit failure handling.
- Bounded CPU feature cache, contiguous float32 descriptor storage and representation fingerprints.
- Checkpoint/source installation manifest, pinned revisions, locked dependencies and a dedicated WSL CUDA environment.
- Benchmark inheritance and IPC publication through the existing orchestrator and singleton FIFO report writer.
- Saved learned-pixel input adapter, with image/evidence checksums. No rematching occurs inside the evaluator.
- Existing report and GUI recognize learned feature scores and provenance. Large per-feature evidence stays on disk; the GUI uses a compact index and at most three detailed pairs in its cache.
- Current adapter archives code/configuration snapshots and records query p50/p95, cache/index memory and peak PyTorch GPU allocation. Reports can live in a different configured directory from native artifacts.

No temporal RANSAC or image-grid gate has been introduced. The initial proposal policy preserves retrieval ordering while retaining all reported local assignments. Transformers can be replaced through compatible adapters; arbitrary descriptor families are not interchangeable without the correct trained matcher.

## Fixed evaluator

The numerical XYZ checker, stereo reconstruction, disparity sampling/reliability logic and evaluator YAML are unchanged from the historical ORB + DBoW2 run. A regression test verifies their file hashes against that saved run.

The learned input adapter supplies original pixel coordinates and assignment IDs to the same preparation process. Model confidence and retrieval scores do not affect the XYZ verdict. Missing reference poses exclude a pair; missing reliable depth remains untestable. Reference poses are absent from LDO inference.

## Full 2 Hz comparison

Report: `evaluation/output/evaluation_2026-10-03_23-21-02_224679_a45890c4.md`.

Sequence: MH_01_easy. Both detectors processed the same 369 chronological inputs, 20-second temporal exclusion and top K = 5. Both cases completed. Their shortlisted image pairs differ; these are complete-configuration results, not an isolated matcher comparison.

| Measurement | ORB + DBoW2 | LDO-MegaLoc-LightGlue |
| --- | ---: | ---: |
| Returned image-pair candidates | 1,635 | 1,635 |
| GT-admitted pairs evaluated | 1,540 | 1,512 |
| Pairs excluded for missing reference poses | 95 | 123 |
| XYZ-supported feature observations | 22,309 | 169,337 |
| XYZ-contradicted feature observations | 2,286 | 5,365 |
| XYZ-untestable feature observations | 30,107 | 279,128 |
| All reported feature observations | 54,702 | 453,830 |
| Contradicted / testable | 9.29% | 3.07% |
| Testable / all reported | 44.96% | 38.49% |

LDO used a 1,024-keypoint cap; the ORB reference used its existing extractor configuration. Counts include repeated observations across candidate image pairs, not unique physical landmarks. LDO supplies many more supported observations in this development replay, but also more absolute contradicted and untestable observations. The lower testable coverage must remain visible.

These results do not establish loop recall, exact correspondence precision or reduced downstream SLAM work. Our geometric evidence uses estimated stereo depth and assumed uncertainty, not supplied ground-truth landmark identity. Independent revisit labels, isolated matching/retrieval comparisons and an untouched test set remain necessary.

### Full-run resource measurements

LDO inference and artifact publication took 163.0 seconds, excluding offline XYZ evaluation. Peak PyTorch GPU allocation was approximately 1.26 GiB. The retained CPU feature cache was approximately 129.5 MiB; the descriptor array allocation was 16.5 MiB. These measurements describe the recorded run and exclude other processes/driver allocations. Numerical XYZ evaluation of the larger correspondence set contributes additional offline runtime.

Main LDO evidence:

`evaluation/output/native/ldo/a45890c4ba5941739e86664e6a4790da_1e8436043e73433a80a407990c1055c5/candidate_checks/`

## Final verification

- 74 tests pass, including existing evaluation regressions and new chronology, compatibility, failure, evidence-integrity, lazy-cache and report-path tests.
- Ruff lint and formatting checks pass on new LDO, benchmark, input-adapter, lazy-evidence and test modules.
- `uv lock --check` passes; the dedicated CUDA runtime was synchronized with the lock and `ldo` extra.
- Real pretrained GPU encoding, extraction and pair assignment were exercised.
- A full 2 Hz ORB/LDO comparison completed using the unchanged numerical evaluator.
- The final source-snapshot/resource-reporting code completed a separate 0.2 Hz full-sequence integration check. That sparse check validates plumbing and is not substituted for the main comparison.
- A contradicted-feature preview was rendered and visually inspected: original pixel markers, learned match confidence, stereo depths, world XYZ, unchanged threshold and per-pair feature counts are displayed correctly.

The legacy report writer's assumption that all image artifacts must be under the report directory was corrected after the separate-output integration check exposed it. Relative configuration paths are normalized before snapshotting. Both fixes have regression tests.

## Run and review

From the project root on Windows:

```powershell
uv run python evaluation/run_wsl.py
```

After installation, this runs the configured ORB reference and LDO workers through the existing orchestrator. See `ldo/README.md` for locked CUDA setup and pinned model installation.

To review the full LDO result specifically:

```powershell
uv run python evaluation/view_suspicious.py --checks "evaluation/output/native/ldo/a45890c4ba5941739e86664e6a4790da_1e8436043e73433a80a407990c1055c5/candidate_checks"
```

Use the four feature filters and previous/next navigation; copied flow evidence identifies the selected configuration and matcher score. No ground-truth data enters production inference.

## Related documents

- [Architecture and replaceable interfaces](ldo-architecture-plan.md).
- [Model research and experiment plan](ldo-model-research-plan.md).
- [Local matching research](ldo-local-matching-research.md).
- [Current feature XYZ evaluation](feature-xyz-evaluation.md).
