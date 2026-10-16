# Contribution roadmap

LDO v0.1.0 is a visual research preview. The baseline remains confidence 0.3.
The priorities below are opportunities for contributions, not promised capabilities
or a schedule. Track concrete work in [issues](https://github.com/Elaybarnoam/LDO/issues).

## Start without a GPU

- [Issue #1: verify a clean Linux CPU installation](https://github.com/Elaybarnoam/LDO/issues/1), including the exact OS/Python/uv versions,
  commands, expected smoke output and troubleshooting discovered during setup.
- [Issue #2: improve the missing-model-root diagnostic](https://github.com/Elaybarnoam/LDO/issues/2) while preserving machine-readable
  doctor output and avoiding downloads or heavyweight model imports.
- [Issue #3: add accessible text alternatives](https://github.com/Elaybarnoam/LDO/issues/3) to the correspondence viewer.
  Use a tiny generated fixture; no research images or checkpoints are required.

See [starter issues](https://github.com/Elaybarnoam/LDO/issues?q=is%3Aissue%20is%3Aopen%20label%3A%22good%20first%20issue%22)
and [contributing](../CONTRIBUTING.md) for local validation and scientific boundaries.

## Research contributions

- [Issue #4: a dataset adapter](https://github.com/Elaybarnoam/LDO/issues/4) with explicit timestamp, coordinate, calibration and split
  contracts. Choose a new environment with suitable permissions; do not relabel
  inspected OldTownFall or Factory/Desert observations as a fresh test.
- [Issue #5: a retrieval scaling benchmark](https://github.com/Elaybarnoam/LDO/issues/5) measuring exact-index latency and memory as
  history grows, with deterministic CPU inputs and machine details.
- A small end-to-end learned-model demo with permitted image redistribution,
  saved original assignments, an observed accepted/rejected decision and a
  trajectory view. The current animation reviews archived simulated failures;
  it is not a live replay or real-world validation.

Model changes need predeclared promotion rules and event retention checks.
IMU integration and downstream SLAM benefit require separate interfaces and
protocols; neither is an implemented capability in this release.

## Discussion and review

Use [Q&A](https://github.com/Elaybarnoam/LDO/discussions/categories/q-a) for setup,
Ideas for proposals and Announcements for release notes. Small fixes can go
straight to a pull request; discuss substantial research changes before investing
in expensive experiments. Report reproducibility problems even if you cannot fix
them. Review is maintained on a best-effort basis; no response-time guarantee is
implied.
