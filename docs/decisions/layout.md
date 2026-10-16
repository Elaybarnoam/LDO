# Decision: installable research layout with immutable historical evidence

**Date:** 2026-10-15. **Baseline:** `3d615dcee97e8e74a6c04ec38435be3f249d75c8`.

Runtime packages retain their import names under `src/`. Evaluation adopts
`loop_eval` instead of generic top-level `tasks`, `modules`, and `benchmarks`.
Existing root evaluation launchers remain thin delegates after installation;
historical `python -m tasks...` commands are superseded by `python -m loop_eval.tasks...`.
Exact old command/code replay uses the historical checkout.

Policies and recipes have one editable home under `configs/`, bundled from that
home when building a wheel. Independent numerical evaluator policies remain
separate from operational verification and model selection. Runtime profiles
create new local configuration identities rather than edit published defaults.

The earlier `.docs/` record is moved to `docs/archive/` without changing file
bytes. This deliberately keeps the original flat historical record together
instead of rewriting old protocols and reports into new categories. Current
navigation, methods, protocols, and results indexes supply the new hierarchy.
Historical relative links may refer to the old layout; the migration ledger
provides the authoritative old-to-new mapping.

Bulk `evaluation/datasets`, `references`, and `output` directories stay in place.
New local work belongs under ignored `artifacts/` or explicitly configured external
roots. Completed runs, their source snapshots, and original hashes are unchanged.
Moved/edited live source gets new provenance; old native build manifests naming
moved source must be replaced by fresh builds, not forged to pass validation.

Fingerprint-sensitive `xyz.py`, duplicated stereo workers, and the frozen numerical
XYZ policy retain their bytes. Geometry routines retain their numerical behavior.
Ruff excludes those pinned files from formatting, with narrow existing-style lint
exceptions; the historical archive is excluded entirely.

One repository/build configuration is sufficient. No speculative workflow engine,
new IMU abstraction, automatic model promotion, or numerical threshold change is
part of this layout migration. License selection remains an owner decision.

See the [machine-readable migration ledger](migration-ledger.json) and
[validation record](../validation.md).
