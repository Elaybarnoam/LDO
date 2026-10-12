# LDO implementation

LDO is the visual retrieval and correspondence architecture. `LDO-MegaLoc-LightGlue` is the first frozen-weight configuration: MegaLoc global descriptors, exact cosine search, SuperPoint observations and LightGlue assignments. The shared detector contains no model-name selection logic.

## Run

The existing project uses WSL Ubuntu-24.04 for native benchmarks. From the project root inside WSL:

```bash
UV_PROJECT_ENVIRONMENT=/opt/loop-detector/ldo-env ~/.local/bin/uv sync --locked --extra ldo
/opt/loop-detector/ldo-env/bin/python -m ldo.install
/opt/loop-detector/ldo-env/bin/python evaluation/src/runner.py
```

The installer verifies pinned source revisions, caches released weights, and records SHA-256 hashes. It does not train anything. Large sources/checkpoints live under `/opt/loop-detector/ldo-models`, outside the codebase. MegaLoc/LightGlue/SuperPoint license provenance is recorded separately in the installation manifest.

After installation, the existing Windows launcher also works:

```powershell
uv run python evaluation/run_wsl.py
```

`evaluation/src/config.yaml` runs the ORB + DBoW2 reference followed by LDO through the existing orchestrator. The LDO worker uses its dedicated CUDA environment. The numerical XYZ checker, stereo/disparity calculations and evaluator config are unchanged. Both configurations use the same chronological MH_01_easy replay, 20-second exclusion and top K = 5.

For reusable, integrity-checked stereo cache evidence, set `LDO_STEREO_CACHE_SOURCE` to a previous run's `stereo_correspondences` directory inside the WSL process. This changes cache reuse only; input/model/worker/policy hashes are checked by the existing evaluator. The normal runner needs no cache override.

## Configuration and replacement

- `ldo/configs/megaloc_lightglue.yaml`: selects inference models, device, budgets, cache size, seed and explicit policy.
- `evaluation/src/benchmarks/ldo/config.yaml`: selects dataset/replay and references the model and unchanged evaluation configs.
- `configuration.py`: adapter factories in `ENCODERS`, `ENGINES` and `POLICIES`. Add a compatible factory and select it by configuration; do not branch on model names inside `Detector`.
- `contracts.py`: typed, immutable feature and correspondence records, plus structural model interfaces. A sparse engine composes an extractor and a compatible matcher. A future image matcher needs an adapter to these observation/assignment contracts; it cannot silently reuse incompatible sparse descriptors.

Index fingerprints reject descriptors from a different model/preprocessing space. Local caches are bounded and hold CPU arrays. Historical descriptors use a geometrically growing contiguous float32 allocation. Frames are queried before insertion; temporal eligibility is applied before selecting top K. Failures do not insert partially processed keyframes.

Features and image sizes always use original camera pixels. Optional `feature_resize` controls extraction resolution; the upstream extractor maps points back to original coordinates before matching or evaluation. Every reported assignment is saved, including scores and feature IDs. No temporal RANSAC or grid gate is introduced. The initial proposal policy preserves retrieval rank and exposes local evidence; its scores are not calibrated loop probabilities.

### Pretrained matching optimization

`ldo/configs/optimized-matching.yaml` selects the configuration frozen by the
[matching optimization task](../evaluation/src/tasks/matching_optimization/README.md).
The selected model uses SuperPoint with 1,024 keypoints, native resolution and
adaptive LightGlue at confidence 0.4. The previous confidence-0.3 configuration
remains in `optimized-confidence.yaml`.

On the fresh test, 0.4 removes 17.3% of incorrect feature matches and retains
96.7% of correct matches, but events with at least 20 correct matches fall from
13/17 to 12/17. Treat it as experimental; retain 0.3 when event retention is the
priority. No existing benchmark configuration is switched automatically.

`superpoint_lightglue` and `aliked_lightglue` are interchangeable matching adapters.
ALIKED uses its own extractor and compatible pretrained LightGlue weights;
descriptor families cannot be mixed. `build_pair_engine` constructs the same
production matching adapter without loading retrieval, allowing identical-pair
experiments. Neither adapter receives reference depth or poses.

The task tests confidence, inference depth, keypoint count, resolution and ALIKED
sequentially, then evaluates the frozen choice on fresh OldTownFall trajectories.
See the [protocol](../.docs/ldo-matching-optimization-plan.md) and
[recorded results](../.docs/ldo-matching-optimization-results.md).

## Results and review

The existing singleton FIFO file handler owns the shared timestamped JSON/Markdown reports. Workers publish through the inherited benchmark publisher. Model-specific artifacts live under `evaluation/output/native/ldo/<run>/`:

```text
model_manifest.json           # Source/weights/configuration/runtime provenance
runtime.json                  # Inference/cache/GPU allocation measurements
replay.tsv                    # Exact chronological image list
retrieval.jsonl               # Candidate IDs, scores, counts and timings
learned_features/             # Original pixels and saved match assignments
candidate_checks/             # Existing per-feature XYZ evidence and summaries
stereo_correspondences/       # Existing frozen stereo evidence/cache
```

On Windows, open the existing feature review GUI:

```powershell
uv run python evaluation/view_suspicious.py
```

It chooses the latest completed evidence. Use `--checks <candidate_checks path>` to select a particular run. The feature flow identifies learned match confidence separately from ORB Hamming distance. Colors remain green supported, red contradicted and cyan untestable; navigation and copied evidence remain feature-level.

The viewer scans compact pair/verdict indexes and keeps at most three detailed pairs in its cache. Large learned-match evidence files remain on disk rather than retaining every feature dictionary in RAM. Each lazily loaded pair is checked against its indexed line hash.

## Verification

```bash
/opt/loop-detector/ldo-env/bin/python -m pytest -q
/opt/loop-detector/ldo-env/bin/ruff check ldo tests evaluation/src/benchmarks/ldo evaluation/src/tasks/feature_matching/xyz/learned_features.py
/opt/loop-detector/ldo-env/bin/ruff format --check ldo tests evaluation/src/benchmarks/ldo evaluation/src/tasks/feature_matching/xyz/learned_features.py
```

Tests cover chronology, eligibility before top K, representation compatibility, bounded caches, invalid assignments, source-image/evidence integrity, learned-input handoff, reporting and existing regressions. Local regression checks preserve the historical numerical XYZ/policy hashes and the numerical triangulation/covariance functions. Stereo preparation has explicit field-of-view recovery; see the coverage investigation.

### Stereo coverage and abstentions

Stereo preparation version 2 preserves the original disparity path and attempts expanded-field recovery only for observations outside its usable domain. Recovered observations still pass the existing left/right, depth, parallax, uncertainty and XYZ gates. The preparation never selects depth based on a temporal correspondence or reference pose. A second rectified input increases offline evaluation cost.

Reports retain all matches in the denominator and show coverage within the primary rectified domain separately from additional raw-image coverage. ORB's native extractor operates on rectified images; comparing aggregate coverage alone can hide this input-domain difference. Joint query/history failure counts are exclusive, while per-side reason incidences overlap.

Analyze a completed result without running either detector again, from `evaluation/src` in WSL:

```bash
/opt/loop-detector/ldo-env/bin/python -m tasks.feature_matching.xyz.coverage_analysis \
  --checks ../output/native/ldo/<run>/candidate_checks \
  --output /path/to/new-coverage-profile.json
```

The analysis validates completed totals, fingerprints the evidence and counts unique timestamp/feature observations separately from repeated correspondence observations. Neither count is a count of unique world landmarks. See `.docs/stereo-coverage-investigation.md` for recorded measurements and physical limitations.

This implementation is standalone detector evaluation. Native SLAM correction is not executed by this benchmark. Feature XYZ evidence is not a complete loop-accuracy oracle; independent revisit labels and held-out data are required for recall and false-loop claims. Fine-tuning and dedicated LDO transformers are subsequent named configurations.
