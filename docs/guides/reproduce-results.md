# How to reproduce LDO's public results

This guide regenerates tables, figures and the evidence walkthrough from tracked
historical summaries. It establishes presentation agreement with saved evidence.
It does not repeat model inference, restore undistributed raw files or establish
new scientific performance.

## 1. Start from a checkout

```bash
git clone https://github.com/Elaybarnoam/LDO.git
cd LDO
uv sync --locked --extra visualization
uv run ldo-research smoke --output artifacts/smoke.json
```

Use Python 3.11. These documentation guides are on `main`; the earlier `v0.1.0`
release contains the original tools and research preview. Record your actual
commit with `git rev-parse HEAD` when reproducing results.
The smoke output must explicitly say `research_result: false`.

## 2. Regenerate evidence presentations

```bash
uv run python scripts/reproduce/publish.py --output artifacts/reproduced-results --figures artifacts/reproduced-figures
uv run python scripts/figures/render_diagrams.py --output artifacts/reproduced-diagrams
uv run python scripts/figures/render_community.py --output artifacts/community
uv run python scripts/check_repository.py
```

The publication command indexes eight studies. Each output study contains a
manifest, `metrics.json`, `table.csv` and `table.md`; the result root also contains
`index.json`. Scientific figures include PNG/SVG/PDF exports. The community
renderer produces the 24-second GIF, static poster, social preview and a manifest.
Outputs stay under ignored `artifacts/`; historical source files are preserved.

## 3. Check the headline measurements

For the same OldTownFall LDO retrieval identities:

| Measurement | Baseline confidence 0.3 | Experimental confidence 0.4 |
| --- | ---: | ---: |
| Supported assignments | 40,003 | 38,673 |
| Contradicted assignments | 100,983 | 83,526 |
| Unknown assignments | 9,879 | 8,457 |
| Raw confirmed event hits | 17/17 | 17/17 |
| Events with at least 20 supported matches | 13/17 | 12/17 |

Compare `artifacts/reproduced-results/matching-oldtown/metrics.json` with
[the tracked metrics](../../results/matching-oldtown/metrics.json). Generator and
source hashes in the manifest explain lineage; a changed generator hash is not a
license to rewrite the old source record. Rendering-library differences can change
image bytes even when numerical tables agree.

The existing `check_repository.py` checks tracked source and asset hashes, protected
numerical definitions, active Markdown links, derived metrics and the README
headline table. It does not certify model checkpoints or missing raw experiments.

## 4. Distinguish a scientific rerun

A fresh experiment additionally needs pinned model sources/checkpoints, permitted
datasets, exact input ordering and calibration, original assignments, independent
reference assets, external native/stereo runtimes where applicable, and a frozen
protocol. Record runtime, source/config hashes, data roles and immutable run IDs.

Use [installation](../installation.md), [the full reproducibility guide](../reproducibility.md)
and [correspondence evaluation](evaluate-correspondences.md) for those workflows.
Factory/Desert and OldTownFall have already been inspected; future choices cannot
reuse them while claiming a fresh test. The current baseline remains confidence 0.3.

## 5. Contribute a reproducibility improvement

[Verify a clean Linux installation (#1)](https://github.com/Elaybarnoam/LDO/issues/1)
or [improve missing-model diagnostics (#2)](https://github.com/Elaybarnoam/LDO/issues/2).
Include your commit, OS, Python/uv versions, commands and exact observed output.
If a hash fails, report which artifact changed rather than disabling verification.
