# Independent reference-geometry task

The default experiment evaluates ORB + DBoW2 and LDO feature correspondences directly against TartanAir reference depth and camera poses. Ground truth stays outside both detectors. The original EuRoC XYZ implementation remains unchanged.

## Default topology

```text
Identical camera frames -> ORB + DBoW2 / LDO -> candidates + original feature assignments
                                                   |
Reference depth + camera poses -> world XYZ for each reported endpoint
                                                   |
                                  supported / contradicted / unknown
                                                   |
                              per-feature JSONL + dated JSON/Markdown
```

No learned stereo estimator, PnP, RANSAC, operational verifier, accepted-pair selection or pose-failure count participates in this measurement. Every reported assignment is included. Each saved feature row contains both reference world positions when usable, their XYZ disagreement, reprojection error, and final reference verdict.

## Commands

From the project root:

```powershell
uv run python evaluation/reference_geometry.py install
uv run python evaluation/reference_geometry.py prepare
# Fresh model inference followed by direct reference checks:
uv run python evaluation/reference_geometry.py run --prepared evaluation/output/tartanair_reference_<id>
# Recompute from saved detector traces and assignments, without running models:
uv run python evaluation/reference_geometry.py evaluate --results evaluation/output/tartanair_benchmark_<id>/summary.json
# Render a completed direct evaluation:
uv run python evaluation/reference_geometry.py report --results evaluation/output/tartanair_reference_features_<id>/summary.json
# Separate, optional full observation-stereo + operational-verifier experiment:
uv run python evaluation/reference_geometry.py pipeline --prepared evaluation/output/tartanair_reference_<id>
```

Windows forwards to the installed WSL environment. `evaluate` reuses original detector outputs after checking input and feature hashes; it reads no previous verifier decisions or inlier masks. `run` prepares references when `--prepared` is omitted. Each evaluation creates a new immutable evidence directory.

## Modules

- `cli.py`: validation and dispatch.
- `install.py`, `dataset.py`: pinned installation and source adaptation.
- `detectors.py`: image-only model adapters and original assignments.
- `direct.py`: default direct reference evaluation, fresh or saved detector evidence.
- `direct_report.py`: feature and independently labeled candidate metrics, with unknown bounds.
- `geometry.py`: frozen depth, camera transforms, visibility and feature gates.
- `depth_coverage.py`: reason for each untestable feature.
- `workflow.py`, `reporting.py`: reference preparation and separately requested full-pipeline diagnostics.

## Interpretation

Feature verdicts measure reported correspondence correctness under frozen reference-depth/reprojection tolerances. They do not declare an entire candidate image pair false because some matches are incorrect. Image-pair surface overlap is labeled independently. Unknown matches remain unknown; counts and rates among judgeable features are reported separately, together with bounds accounting for all unknown matches. Zero-match candidate pairs remain in pair-level totals.

The installed pilot uses all seven short ArchVizTinyHouseDay/Data_easy trajectories, identical grayscale images, and a shared 5-second exclusion. It does not establish long-term revisit performance, real-world superiority or OOD generalization. Both detectors currently use camera images only. Depth boundaries and the useful 0.25-50 m depth range can prevent reference judgments. Static-world assumptions and pretrained dataset overlap remain unaudited.

Data remain in WSL `/opt/loop-detector/datasets/tartanair_v2`, indexed by `evaluation/datasets/tartanair_v2/installation.json`. Fresh detector evidence is under `evaluation/output/tartanair_detector_evidence_*`; direct evaluation results are under `evaluation/output/tartanair_reference_features_*`. The existing evaluation file handler publishes dated reports.
