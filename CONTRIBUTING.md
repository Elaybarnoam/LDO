# Contributing

Use Python 3.11 and install the locked environment with `uv sync --locked`.
Run `uv run python -m pytest -q`, `uv run ruff check .`, and
`uv run ruff format --check .` before submitting a change.
Run `uv run mypy` for the incrementally checked contracts/path/profile modules.

Keep numerical/policy changes separate from layout and formatting changes.
Public interfaces must describe shapes, dtypes, frames, units, chronology,
failure semantics, and provenance. Runtime detection and verification must not
import offline reference evaluation or accept its labels as observations.

New experiments need an explicit question, fixed data roles, baseline, metric
denominators, unknown accounting, and promotion rules recorded before selection.
Preserve failed trials and event identities. Do not tune on an inspected test and
continue calling it fresh evidence. See the [protocol guide](docs/protocols/README.md).

Historical evidence in `docs/archive/` is preserved byte-for-byte. Do not format
fingerprint-sensitive workers, `xyz.py`, or the frozen XYZ policy. Numerical changes
require a new policy/evaluator identity, regression checks, and a separate result.
The [migration ledger](docs/decisions/migration-ledger.json) records original paths
and hashes. See [architecture](docs/architecture.md) for package responsibilities.

Project licensing is not yet specified. No license grant is implied by this guide;
upstream model, data, and source terms remain separate.
