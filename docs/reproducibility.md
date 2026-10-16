# Reproducibility and evidence lineage

## What is available

Tracked files include source, locked Python dependencies, live recipes, original
curated reports and JSON summaries, diagnostic images, and compact derived public
tables/figures. Bulk datasets, checkpoints, per-match raw runs, and native builds
remain external. Absolute `/opt/...` locations in archived reports identify the
original machine; they are not public artifact download links.

The [study index](../results/index.json) links each experiment to an evidence
manifest. Manifests hash the original protocol, narrative, and machine-readable
source where available. They explicitly identify themselves as historical
evidence indexes, not complete manifests of newly rerun experiments. Raw evidence
access remains necessary to repeat numerical reference checks.

## Three reproduction levels

| Level | Command / requirement | What it establishes |
| --- | --- | --- |
| Installation | `uv run ldo-research smoke` | Installed production interface works on deterministic synthetic inputs |
| Presentation | Commands below using tracked archived summaries | Public tables/plots agree with saved measurements |
| Scientific rerun | Pinned models, datasets, references, native/stereo runtimes, original protocol, new immutable outputs | Fresh inference or an explicitly versioned reference rescore |

```bash
uv sync --locked --extra visualization
uv run python scripts/reproduce/publish.py --output artifacts/reproduced-results --figures artifacts/reproduced-figures
uv run python scripts/figures/render_diagrams.py --output artifacts/reproduced-diagrams
uv run python scripts/check_repository.py
```

Expected OldTownFall supported/contradicted counts are 40,003/100,983 for confidence
0.3 and 38,673/83,526 for 0.4; unknown counts are 9,879 and 8,457. Raw event hits are
17/17 for both, while the ≥20-supported-match diagnostic is 13/17 and 12/17.
Those values must derive from the tracked JSON, not be hand-edited in tables.

## Full reference workflow

Inside the configured WSL model environment, after external dependencies are
installed:

```bash
uv run ldo-research reference install
uv run ldo-research reference prepare
uv run ldo-research reference run --prepared evaluation/output/tartanair_reference_<id>
```

Replace `<id>` with the actual prepared evidence directory produced by the
preceding command. Commands create new outputs. `reference pipeline` is the
separate optional observation-stereo/verifier experiment; the default `run`
checks all saved original feature assignments directly against reference depth.

For saved detector evidence:

```bash
uv run ldo-research reference evaluate --results /path/to/completed/summary.json
uv run ldo-research reference report --results /path/to/completed/reference/summary.json
```

These commands need the referenced evidence and verify required hashes. A new
checkout cannot recover undistributed raw files merely from a summary JSON.
After moving source, use the historical checkout for exact original-code replay,
or document a new derivation with explicit source/path changes. Never replace an
old code hash or ignore a failed integrity check to force cache reuse.

## Run-record requirements

Record the research question, immutable run ID, protocol revision, dataset roles,
input order, calibration, model/checkpoint/preprocessing identity, fully resolved
configuration, source commit plus dirty state, numerical policy/evaluator version,
runtime packages/builds/hardware, seeds, and artifact hashes. Existing tasks retain
their detailed evidence formats and the singleton report publisher.

Distinguish prepared/running/failed/completed states; validate outputs before a
latest pointer advertises completion. Retain failed trials, zero-match pairs,
unknown reasons, and per-event identities. Report generation consumes saved
evidence independently of model execution. Resume only when source/config/model/
input fingerprints match the run's own declared contract.

## Statistical and runtime scope

Correspondences and nearby frames are dependent. Define paired sequence or
temporal-block analyses appropriate to the research question and available sample
size. The existing event bootstrap requires complete references and reports
within-sequence uncertainty; it is not a cross-environment generalization claim.
Unknown bounds are not confidence intervals.

Runtime studies must separate encoder/search/extraction/matching/stereo/verification
from offline evaluation; specify hardware, synchronization, warmup, cache state,
repeats, and latency distributions. Current curated experiments do not establish
real-time performance, bounded total memory, or downstream SLAM improvement.
