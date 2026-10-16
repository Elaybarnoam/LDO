# Evaluation tasks

Each task owns its evaluation logic and review tools. Benchmark adapters, dataset installation, orchestration, IPC publishing and the singleton report writer are shared.

Implementation plans: `feature_matching/PLAN.md` and `loop_closure/PLAN.md`. The overall protocol is `docs/archive/ldo-orb-validation-plan.md`.

```text
evaluation/
├── compare.py                         # Loop comparison entry point
├── view_suspicious.py                 # Feature evidence entry point
├── datasets/                         # Shared camera/IMU data
├── references/                       # Independent loop reference annotations
├── output/                           # Immutable historical runs and new reports
└── src/
    ├── runner.py                     # Shared benchmark runner
    ├── config.yaml                   # Benchmark orchestration settings
    ├── benchmarks/                   # ORB, LDO and shared benchmark interface
    ├── modules/
    │   ├── orchestrator/
    │   ├── benchmark_publisher/
    │   ├── evaluation_file_handler/
    │   └── events.py
    └── tasks/
        ├── feature_matching/
        │   ├── xyz/                  # Existing independent stereo/XYZ evaluator
        │   │   └── config.yaml
        │   └── viewer/               # Feature-by-feature evidence GUI
        └── loop_closure/
            ├── config.yaml           # Independent loop comparison protocol
            ├── comparison/           # References, annotation, metrics and experiments
            ├── verification.py       # Common runtime verifier replay adapter
            ├── pose_assessment.py    # Offline reference pose errors
            ├── loop_metrics.py       # Accepted connections and missed opportunities
            ├── assessment.yaml       # Independent assessment policy
            └── run.yaml              # Shared supervised benchmark
```

`feature_matching` answers whether reported feature correspondences are geometrically consistent. `loop_closure` answers whether candidate image pairs represent real revisit opportunities, including missed opportunities.

The loop task can invoke the feature task's XYZ evaluator for diagnostic evidence; it never treats individual feature verdicts as independent loop truth. The shared operational relative-pose verifier lives in the project-root `loop_verification/` package. Its replay adapter and independent assessment live in the loop task. The verifier receives no reference poses, labels or XYZ verdicts.

Existing entry commands remain valid. Python module commands now use `loop_eval.tasks.feature_matching.xyz` or `loop_eval.tasks.loop_closure.comparison`. Historical evidence and its saved source snapshots retain their original paths. Current reports continue through the same singleton FIFO writer.

Project-root `stereo_observations/` owns reusable camera-only disparity and geometry. `loop_verification/` owns the operational contracts, stereo depth and PnP acceptance.
