# Verification suites

| Directory | Purpose |
| --- | --- |
| `regression/` | Existing detector, reference geometry, matching, metrics, and evidence regressions |
| `integration/` | Existing process supervision, native protocol, reporting, and review integration checks |
| `unit/` | Installed-command, portable configuration, and publication integrity checks |

Run `uv run python -m pytest -q` from the checkout. Pytest imports installed
packages; no repository `pythonpath` injection is configured. Small synthetic
fixtures stand in for native protocol emitters and do not simulate SLAM accuracy.
The stdlib-only native fixture uses the standalone interpreter to avoid Windows
virtual-environment launcher descendants retaining log handles after termination.

Tests that inspect undistributed historical evidence skip with a reason when it
is absent. Native C++ logger compilation runs on Linux with an available compiler.
No ordinary CPU test downloads checkpoints or datasets. Actual GPU/model/native
experiment runs are separate from these fixture-based checks.

Frozen numerical XYZ/worker bytes and AST-equivalent reconstruction are checked
against the migration baseline and available historical evidence. See
[validation](../docs/validation.md).
