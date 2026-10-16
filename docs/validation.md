# Validation record

**Completed:** 2026-10-16 (Asia/Jerusalem). No scientific inference/rescore was
performed as part of this repository reorganization.

The baseline at `3d615dcee97e8e74a6c04ec38435be3f249d75c8` passed 219 tests with
2 skips and 19 subtests on Windows; Ruff reported 86 pre-existing issues.

| Check | Outcome |
| --- | --- |
| Windows Python 3.11.15 regression/unit/integration suite | **225 passed, 2 skipped, 19 subtests passed** |
| Fresh WSL Ubuntu-24.04 Python 3.11.16 environment | **226 passed, 1 skipped, 19 subtests passed**, including native C++ logger compilation/execution |
| Ruff lint / formatting | Passed across active source, tests, scripts, and current documentation |
| Incremental mypy | Passed for detector contracts, path resolution, runtime profiles, and installed CLI (4 source files) |
| Installed CPU replay and workflow help | Passed; expected chronology/candidate output, no model downloads |
| Wheel and source distribution | Built successfully; wheel installed into an isolated target and exercised outside the checkout |
| Wheel resources | Verified model pins, workers/runtime lock, native build inputs, review HTML, and bundled configuration |
| Historical/pinned preservation | All 82 archived files and four pinned numerical/worker/policy files match original byte hashes |
| Geometry preservation | Numerical function AST hashes match the baseline in five geometry modules |
| Public evidence | Eight historical studies indexed; regenerated metrics and README table agree with saved JSON |
| Figures | Scientific SVG/PDF/PNG outputs generated; previews visually inspected; source/output provenance verified |
| Current documentation | Relative links, image references, fences, and display-math delimiters passed local checks |
| GPU driver diagnosis | Device visible through `nvidia-smi`; no model-runtime/inference validation claimed |

All CPU checks use the locked dependencies. WSL validation used an isolated
`.venv-linux` environment; the existing external native/model environments and
completed experimental outputs were not replaced. Platform skips identify the
Linux-only compiler fixture and unavailable undistributed historical evidence.

Native trace fixtures exercise protocol validation and cleanup, not SLAM accuracy.
The stdlib-only fixture now invokes the standalone interpreter to avoid Windows
virtual-environment redirector descendants holding logs after early termination.

Full CUDA inference, fresh dataset downloads, native ORB rebuilding, and scientific
experiment reruns are separate external-runtime work and are not represented by
the CPU checks. The optional CI runtime workflow reports prerequisites by default.
Its opt-in self-hosted GPU job checks configured model hashes, driver visibility,
and a CUDA tensor operation; it does not advertise a scientific experiment rerun.

Original reports, source snapshots, and data/model manifests remain historical
evidence. New layout/source hashes do not validate old caches. No model promotion,
new numerical result, fresh-test claim, or downstream SLAM improvement is implied.
