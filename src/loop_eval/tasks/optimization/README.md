# Sequential detector optimization

This task compares each change with its predecessor using unchanged independent
TartanAir reference geometry. Reference depth and poses are used only for training
supervision and evaluation. Deployment consumes images and timestamps.

## Split

| Role | Environment | Trajectories |
| --- | --- | --- |
| Training | RetroOffice | P000–P005 |
| Development fit | ArchVizTinyHouseDay | P000–P004 |
| Development selection | ArchVizTinyHouseDay | P005–P006 |
| Held-out evaluation | CountryHouse | P000–P005 |

TinyHouse was already examined before this experiment. Its development results
are selection results. CountryHouse is evaluated only after all choices are frozen.
Upstream pretrained exposure is unknown; this split does not establish complete
out-of-distribution evaluation.

## Run

Use the installed WSL model environment, from the project root:

```bash
export PYTHONPATH=.:src/loop_eval
PY=/opt/loop-detector/ldo-env/bin/python
$PY -m loop_eval.tasks.optimization.install_data
$PY -m loop_eval.tasks.optimization.develop
$PY -m loop_eval.tasks.optimization.training
$PY -m loop_eval.tasks.optimization.heldout prepare
$PY -m loop_eval.tasks.optimization.heldout run
$PY -m loop_eval.tasks.optimization.verify_runtime
```

`develop` uses the pinned completed TinyHouse direct-evaluation report named in
`develop.py`. It verifies original assignments and reference artifact hashes.
The task therefore requires that local experiment evidence; it is not a generic
download-and-run benchmark on another machine yet.

Training caches immutable SuperPoint observations under
`/opt/loop-detector/ldo-optimization`, adapts 66,049 assignment-head parameters for
300 updates, and keeps attention/extraction/retrieval frozen. Invalid or ambiguous
training geometry is ignored, not labeled negative. A full-depth pretrained
control distinguishes computation changes from learning. Adaptation is promoted
only when development performance improves over both the predecessor and the
equal-compute control, retaining at least 90% of supported matches.

CountryHouse also installs real synchronized right images because the pinned
native ORB exporter expects both cameras. Neither detector's retrieval/matching
decisions nor the independent direct scorer uses cam1 in this experiment.
RetroOffice training needs only left images, left reference depth and poses.

## Outputs and deployment

- `evaluation/output/optimization/development/step1.json`: confidence sweep and validation.
- `step2.json`: fitted candidate policy and validation.
- `step3.json`: real training losses, gradients, checkpoint scores and promotion decision.
- `evaluation/output/optimization/heldout/frozen_variants.json`: choices frozen before test inference.
- `results.json`: every held-out variant, step changes, unknowns and ORB comparison.
- `runtime_verification.json`: production detector versus offline filtering parity.
- Dated `evaluation/output/comparison_*.md` and `.json`: reports published by the shared FIFO file handler.

Deployable configurations live in `configs/models/optimized*.yaml`. They are opt-in;
the existing baseline configuration and original EuRoC XYZ evaluator remain intact.
Checkpoints are external, hash-checked, strictly loaded, and require full-depth
inference so early exits cannot bypass an adapted final head.

Correct/incorrect feature matches, known candidate TP/FP, unknown evidence and
confirmed-event hits are separate metrics. A policy that discards good candidates
can reduce false returns without improving overall detection. The report preserves
these losses explicitly. No test result changes thresholds or model selection.
