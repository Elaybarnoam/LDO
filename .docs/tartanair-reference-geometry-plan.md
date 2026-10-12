# TartanAir V2 independent reference-geometry pilot

## Purpose
Measure candidate retrieval, actual reported feature correspondences, and accepted relative-pose constraints independently. Preserve the existing EuRoC XYZ evaluator unchanged; this new task adds simulator-reference depth as an independent measurement to diagnose the previously low stereo evaluation coverage.

## Frozen pilot protocol
- Dataset: pinned TartanAir V2 revision `0d2d145e973832742a2aaa04b7d2ebffc8d82817`, ArchVizTinyHouseDay/Data_easy, all seven P000?P006 trajectories.
- Replay: identical grayscale 640x640 front stereo, every fifth source frame (2 Hz); reset detector histories between trajectories. Actual camera timestamps, no fabricated IMU samples.
- The source trajectories last only 9?15 seconds. A separate pilot configuration uses a **5-second exclusion** equally for ORB and LDO. The previous 20-second protocol produced zero eligible pairs. This is short-sequence pipeline validation, not a long-term loop-closure benchmark.
- Both methods return at most five candidates per query; report K=1 and K=5. No model training, no parameter selection using detector outcomes.
- Reference universe: every temporally eligible sampled frame pair, prepared before detector inference. Fixed grid, depth/pose transformation, occlusion and bidirectional visibility establish geometric surface overlap.
- Loop label: lower bound on minimum directional overlap >=20%; non-loop if its upper bound is <20%; otherwise unknown. Missing or boundary depth widens the interval. Behind-camera and out-of-image points are known non-overlap. This replaces an unnecessarily restrictive whole-image 90% depth-quality gate, before detector inference. All numerical tolerances live in the versioned task config. Labels establish overlap under this policy, not semantic place identity.

## Topology
```text
Pinned archives -> hash-verified installation
  -> source adapter -> identical grayscale replay + calibrated stereo
                    -> reference depth/pose -> frozen all-pair labels + continuous events
Replay -> ORB + DBoW2 -> ranked candidates + native ORB assignments --+
Replay -> replaceable frozen LDO -> ranked candidates + assignments --+
                                                                    |
             +------------------------------------------------------+
             |                       |                          |
       independent depth/pose  observation-only stereo      independent reference
       per-feature XYZ checks  -> same PnP verifier          overlap/event scoring
                               -> GT pose assessment
             +-----------------------+--------------------------+
                            append-only evidence + hashes
                            -> dated JSON and Markdown report
```

Reference depth/poses never enter either detector or operational verifier. Existing XYZ evaluation code and its policy remain unchanged. This task measures a separate independent oracle, avoiding reliance on a learned stereo estimator for reference correctness.

## Files
`evaluation/reference_geometry.py` is the entry point. `evaluation/src/tasks/reference_geometry/` owns config, dataset installation/adapter, geometry, frozen detector adapters and workflow. `evaluation/datasets/tartanair_v2/installation.json` indexes WSL data. `evaluation/output/tartanair_reference_*` freezes reference inputs; `tartanair_benchmark_*` stores traces, every feature verdict, constraints, hashes and source snapshots. The existing evaluation file handler publishes dated comparison reports.

## Measurements
Report candidate TP/FP/unknown under the overlap policy; event recall, with overall recall withheld if the universe contains unknown reference labels; per-feature supported/contradicted/untestable counts and judgeable coverage; accepted constraints and pose errors at the frozen 0.20 m/5 degree tolerance. Unknown is never counted as false. Continuous returns are grouped into events, not independent successful closures. Development precision thresholds and temporal-block uncertainty are diagnostics only, not held-out validation.

## Gates and limitations
Test pose axes, packed depth, visibility/occlusion, reference-depth boundaries, incorrect and correct feature correspondences, and unknown semantics. Check real stereo baseline against simulator depth before comparing models. Retain all trajectories and report them individually. This is one synthetic environment with a provisional static-world assumption, unaudited pretrained training overlap, and short temporal separation. Neither detector currently consumes IMU. It cannot establish real-world superiority or OOD performance; that requires independent real sequences and a held-out protocol.

## Commands
```powershell
.\.venv\Scripts\python.exe evaluation/reference_geometry.py install
.\.venv\Scripts\python.exe evaluation/reference_geometry.py prepare
.\.venv\Scripts\python.exe evaluation/reference_geometry.py run --prepared evaluation/output/tartanair_reference_<id>
```
Windows entry points forward GPU work into the installed WSL environment.

## Implemented report diagnostics
The report separates raw top-K proposals, accepted geometric constraints, and independently measured pose failures. K=1 and K=5 retrieval metrics include precision bounds when some pair labels remain unknown. A hash-checked depth-coverage analysis explains each untestable reported feature match using the first failing gate across either endpoint: image bounds/nonfinite coordinates, nonfinite depth, useful depth range, or depth boundary. This analysis verifies that its reason codes reproduce the frozen evaluator's validity masks and does not change any verdict.

Use `evaluation/reference_geometry.py report --results evaluation/output/tartanair_benchmark_<id>/summary.json` to regenerate a dated report without detector inference. Final reports retain the inference source hashes and record separate reporting/coverage-analysis hashes. Future runs also snapshot all five model/verifier/assessment configuration files.

## Updated default: direct model correspondence evaluation (2026-10-09)

The default `run` command now measures every original ORB/LDO feature assignment directly against simulator reference depth and camera poses. `evaluate --results <saved-summary>` repeats this measurement from integrity-checked saved model evidence without model inference. The operational stereo/PnP/RANSAC experiment is explicitly separate under `pipeline`.

The reference geometry, depth masks and thresholds are unchanged. We remove operational pose estimates and acceptance gates from the default measurement, rather than tuning the evaluator to obtain better results. Reference poses transform each backprojected feature into the same world frame; corresponding world positions should agree within the frozen XYZ and symmetric reprojection tolerances. Saved numerical evidence includes both world coordinates. Each feature is supported, contradicted or unknown independently, and all assignments are counted, regardless of previous operational acceptance.

`direct.py` owns this default evaluation and `direct_report.py` owns its aggregation/report. Existing report rendering dispatches by explicit experiment mode. Pair-level overlap/event labels remain independent, and a contradicted feature is not automatically a false loop-closure pair. Report coverage, judgeable accuracy, absolute counts, zero-match pairs and all-match bounds. Tests require that corrupted original traces and partial sequence evidence fail, and that direct evaluation runs even when previous verifier decision files are unreadable and operational constructors are forbidden.
