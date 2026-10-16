# Contributing

Welcome. Start with [good first issues](https://github.com/Elaybarnoam/LDO/contribute)
or the [contribution roadmap](docs/roadmap.md). Beginner tasks should run on CPU
without checkpoints or dataset downloads. Ask setup questions in
[Q&A](https://github.com/Elaybarnoam/LDO/discussions/categories/q-a); use issues for
reproducible bugs and agreed work, and Ideas for early research proposals.

For a small fix, fork the repository, create a focused branch, make the change,
run the relevant checks below, and open a pull request explaining the problem,
resulting behavior and validation. Large research changes should start with a
protocol discussion. You do not need to reproduce every GPU study to improve
documentation or tooling. State which checks you could run and which need help.

Use Python 3.11 and install the locked environment with `uv sync --locked`.
Run `uv run python -m pytest -q`, `uv run ruff check .`, and
`uv run ruff format --check .` before submitting a change.
Run `uv run mypy` for the incrementally checked contracts/path/profile modules.

Use fenced `math` blocks and protected inline expressions for GitHub mathematics;
see [GitHub's math syntax](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/writing-mathematical-expressions).
Run `uv run python scripts/check_github_math.py` with authenticated `gh` to verify
GitHub preprocessing, then inspect the published equations in a browser. The
preprocessing check sends the selected public Markdown to GitHub's rendering API;
it does not replace client-side visual verification.

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

Original project contributions use Apache-2.0; GPL instrumentation contributions
retain their directory's license. Submit work you have permission to contribute
and preserve third-party notices. See [licensing](docs/licensing.md).
Review is best-effort; small, reproducible changes are easier to assess.
