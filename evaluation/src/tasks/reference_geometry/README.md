# Independent reference-geometry task

This task compares frozen ORB + DBoW2 against LDO-MegaLoc-LightGlue using TartanAir V2 simulator depth and camera poses as external references. It is separate from the existing EuRoC feature-matching and loop-closure tasks. The original XYZ implementation is unchanged.

## Entry points
Run from the project directory:

```powershell
.\.venv\Scripts\python.exe evaluation/reference_geometry.py install
.\.venv\Scripts\python.exe evaluation/reference_geometry.py prepare
.\.venv\Scripts\python.exe evaluation/reference_geometry.py run --prepared evaluation/output/tartanair_reference_<id>
.\.venv\Scripts\python.exe evaluation/reference_geometry.py report --results evaluation/output/tartanair_benchmark_<id>/summary.json
```

Windows routes execution to the installed WSL environment. Installation pins archive revision, size and SHA256. Data reside in `/opt/loop-detector/datasets/tartanair_v2`; `evaluation/datasets/tartanair_v2/installation.json` is the project index. `run` also prepares references if `--prepared` is omitted. A run always creates a fresh evidence directory. `report` reuses saved evidence and does not run either detector.

## Boundaries
- `cli.py`: validated configuration and command dispatch.
- `install.py`: archive download, validation and safe extraction.
- `dataset.py`: source timestamps, calibrated detector replay and stereo reference audit.
- `geometry.py`: independent depth/pose reference labels and feature judgments.
- `detectors.py`: frozen ORB and replaceable LDO adapters; detector inputs contain no reference depth or poses.
- `workflow.py`: prepare references, run adapters, shared observation-only verification and evidence output.
- `depth_coverage.py`: explains untestable reference-depth checks without changing decisions.
- `reporting.py`: aggregate saved measurements and render readable reports.

## Outputs
Frozen reference directories contain replay images, calibration, frame and input hashes, all eligible pair labels, event definitions and a manifest. Benchmark directories contain model traces, exact extracted feature assignments, every feature verdict, operational verifier decisions, independent pose assessments, source snapshots and per-trajectory summaries. The evaluation file handler publishes dated Markdown and JSON reports.

## Scope of the installed pilot
All seven ArchVizTinyHouseDay/Data_easy trajectories are used. They last only 9 to 15 seconds, so a dedicated 5-second exclusion replaces the inapplicable 20-second EuRoC exclusion equally for both methods. This is a short synthetic pipeline pilot. It cannot establish long-term revisit performance, real-world superiority or OOD generalization. Neither current detector consumes IMU, although the source IMU files are installed.

A candidate is a retrieval proposal. An accepted constraint is the shared operational verifier's decision. A surface-overlap label and a relative-pose tolerance check measure separate properties. Unknown labels are never counted as incorrect. See `.docs/tartanair-reference-geometry-plan.md` for the protocol and limitations.
