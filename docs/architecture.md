# Architecture and module interfaces

## Package responsibilities

| Package | Interface and responsibility | Permitted dependencies |
| --- | --- | --- |
| `ldo` | `Detector.process_keyframe` returns ranked candidates and original local assignments | Model adapters, numerical/image libraries; no offline reference modules |
| `loop_verification` | `VerificationInput` → relative-pose result and operational diagnostics | Observation-only stereo and geometry; no reference labels/poses |
| `stereo_observations` | Calibrated image-only disparity and metric reconstruction | Camera observations, model worker, calibration |
| `loop_eval` | Dataset/benchmark adapters, reference assessment, orchestration, reports, diagnostics | Runtime packages and independent references |

Dependencies point from research evaluation toward runtime packages. Runtime
packages do not depend on the evaluation package. The import-separation regression
inspects actual files under `src/`, including the new `loop_eval` namespace.

## Detector seams

`GlobalEncoder.encode(image)` provides a normalized descriptor and a representation
fingerprint. `PairEngine.extract(image)` / `match(query,history)` provide compatible
local observations and assignments. `ProposalPolicy.apply(query,candidates)`
selects proposals using available runtime evidence. Factories choose adapters;
`Detector` does not branch on model names.

The interfaces include temporal ordering, session identity, array shapes/dtypes,
coordinate frames, mutability, error modes, and model identity. See
[notation](notation.md) for these invariants and [source contracts](../src/ldo/contracts.py)
for the executable validation. Pair-dependent image matching has a separate
[pixel-correspondence interface](../src/ldo/matching/image_pairs.py).

## Evaluation structure

`loop_eval.benchmarks` adapts LDO, ORB + DBoW2, and separately instrumented
ORB-SLAM3 to shared events. `loop_eval.infrastructure` owns process supervision,
publishing, and the singleton FIFO evaluation writer. `loop_eval.tasks` owns
specific evaluation protocols and scientific experiments. Task-specific viewers
stay with their evidence; shared visualization is extracted only when reused.

The report writer remains the owner of dated final JSON/Markdown reports.
Workers publish ordered events and detailed artifacts. Completion is not inferred
from the existence of an output directory. Cancellation/cleanup and strict native
trace validation are exercised by integration fixtures.

## Source and configuration

Runtime packages live in `src/`; complete live policies/recipes live in `configs/`.
The [configuration catalog](../configs/README.md) documents their roles. Wheels
bundle those same files into `ldo_research_resources/configs/`, avoiding a second
editable source of defaults. A native build requires the checkout and external
upstream source, compiler, vocabulary, and libraries.

Current research tasks use a checkout root to locate datasets, evidence, and
source snapshots. Pure installed imports, diagnosis, and the CPU smoke work
outside the checkout. Full experiments are checkout workflows with explicit
runtime profiles; they are not a self-contained wheel-only benchmark download.

## Preservation constraints

The layout change preserves numerical XYZ checks, worker bytes, and historical
evidence. Imports, configuration locations, and source snapshot paths change and
therefore legitimately get new hashes. Old caches/manifests must not be edited to
appear compatible. New native manifests require a fresh build at a separate path
when old manifests name moved source files.

See [migration decisions](decisions/layout.md), [reproduction](reproducibility.md),
and the [equation-to-code map](method.md#9-definition-to-code-audit).
