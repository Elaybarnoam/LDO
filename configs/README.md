# Configuration catalog

| Directory | Responsibility |
| --- | --- |
| `models/` | Named LDO inference variants and their model/policy choices |
| `verification/` | Observation-only operational acceptance and stereo runtime |
| `evaluation/` | Independent reference policies and experiment-specific recipes |
| `benchmarks/` | LDO, component ORB + DBoW2, and native ORB-SLAM3 adapters |
| `runtime/` | Shared orchestrator launch recipes |

The retained research baseline is
[`models/optimized-confidence.yaml`](models/optimized-confidence.yaml), confidence
0.3, 1,024 SuperPoint keypoints, five-second exclusion, and top five retrievals.
[`models/optimized-matching.yaml`](models/optimized-matching.yaml) is the separate
experimental confidence-0.4 variant. The original `megaloc_lightglue.yaml` has
different threshold/exclusion values and must not be silently substituted.

`optimized-policy.yaml` and `optimized.yaml` use the included frozen
`candidate-confidence.json` parameters. These are historical research recipes,
not recommended defaults; model installation and any separately generated
training artifacts remain external.

Files containing `/opt/loop-detector` preserve the established runtime example.
Use `ldo-research configure` and `LDO_CONFIG_ROOT` for another machine; see
[installation](../docs/installation.md). Numerical evaluator settings must be
versioned separately from detector selection. Do not relax the reference policy
after inspecting a method's outputs and report the result as the original study.
