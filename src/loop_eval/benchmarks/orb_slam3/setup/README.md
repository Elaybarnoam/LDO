# ORB-SLAM3 setup and execution

Run the complete evaluation pipeline in Linux/WSL Ubuntu. The Windows `.venv`
cannot run Linux binaries. Native children inherit the adapter's Linux process
group, which the existing orchestrator supervises.

From the project directory inside WSL:

```bash
python3 src/loop_eval/benchmarks/orb_slam3/setup/build.py --install-dependencies
python3 src/loop_eval/benchmarks/orb_slam3/setup/stage_euroc.py --dataset-root evaluation/datasets/euroc --sequence MH_01_easy
export UV_PROJECT_ENVIRONMENT=/opt/loop-detector/python-env
uv sync --python 3.11
uv run python src/loop_eval/runner.py
```

Use a separate Linux virtual environment by setting `UV_PROJECT_ENVIRONMENT`
to a Linux path, for example `/opt/loop-detector/python-env`, before `uv sync`
and `uv run`. This keeps the Windows environment intact. Dependency installation
requires root/sudo; the build can use another writable `--prefix`. Update native
paths in the adapter configuration if the prefix changes.

The build downloads official archives, validates SHA256 checksums, applies
checked patches to the pinned source, and records source/compiler/settings and
binary/library hashes in `evaluation-build.json`. Compilation happens before
evaluation timing. Existing build receipts reject changed patch definitions;
use a fresh prefix to build a changed instrumented version.

For hook updates against the same pinned upstream/dependency revisions, use
`build.py --refresh-instrumentation --orb-archive evaluation/orb-source.tar.gz`.
This verifies existing native artifacts, restores only the six instrumented
upstream files from the checksum-verified archive, reapplies checked patches,
and reuses compiled dependencies. Source revisions cannot change through this mode.
Instrumentation version 6 adds solver internals, candidate selection and completeness checks, gate measurements and rejection reasons, as well as source timestamps for both frames, query eligibility,
per-attempt verification times and final native loop decisions. The outer IPC
protocol and shared loop payload contract are both version 1.

The adapter config supplies Pangolin's library directory explicitly for the
dynamic loader. Setup verifies the loader before writing its build manifest.
Live native logs and trace files stay on Linux under `/opt/loop-detector/runs`;
the adapter exports completed or failed-run artifacts to
`evaluation/output/native/orb_slam3`. This avoids concurrent trace reads across
WSL's OneDrive mount. The report includes both native and exported artifact paths.

Stage each configured sequence before evaluation. The staging script copies its
already-installed ZIP onto Linux, verifies the recorded SHA256 and every entry's
CRC32, then atomically publishes the cache. Only MH_01_easy is staged initially;
the original 11-sequence installation stays in the project. The adapter checks
the cache receipt against the source archive metadata and records both paths.
This avoids timing thousands of image reads through OneDrive during SLAM replay.

Pangolin 0.8 disables its unused FFmpeg input backend and force-includes cstdint
for modern compiler compatibility. ORB-SLAM3 uses C++14 for that dependency.
The upstream example already disables the viewer. Shutdown drains queued mapping
and loop work and awaits native threads before saving trajectories. That lifecycle
change is recorded separately from measurement instrumentation.

## Measurement definitions

- `loop_proposed`: a valid, non-neighbor same-map BoW candidate entering matching /
  geometry, or an existing same-map hypothesis entering temporal refinement.
- `loop_verified`: the same attempt's result. BoW acceptance means the optimized
  projection threshold (80 matches) passed. Refinement acceptance means the
  upstream refinement method returned true. Covisibility confirmations and the
  inertial rotation gate still decide whether correction proceeds.
- `constraint_inserted`: both loop edges were added in `CorrectLoop()`.
- `loop_query`: each processed query, with eligibility and its original gate reason,
  so queries producing zero candidates are retained for evaluation.
- `loop_decision`: the final native acceptance/rejection after confirmation and
  inertial checks, before correction begins.
- Cross-map proposals/results use `map_merge_proposed` / `map_merge_verified`;
  `map_merge` records completed native merging, with map IDs captured beforehand.
- Every proposal/result has an `attempt_id` and `stage`. Repeated attempts are
  measurements, not independent physical revisits. `timing` records tracking and
  place-recognition seconds. A required ready/finished handshake catches incomplete
  or uninstrumented executions.

Timestamps come from the original integer camera timestamp file. The logger
looks up the exact floating-point timestamp representation used by the upstream
reader; it never reconstructs nanoseconds from rounded seconds.

TP/FP/FN remain unavailable until an independent loop ground-truth evaluator is
implemented. Acceptance and correction are not ground-truth labels. The first
MH_01_easy run is a development integration check, not an OOD result. The global
seed does not make ORB-SLAM3's thread scheduling deterministic.
