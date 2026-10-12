# Frozen unseen-environment evaluation

Runs the existing confidence-only LDO (`match_threshold: 0.3`) and pinned native
ORB + DBoW2 on all Data_easy trajectories in AbandonedFactory2 and DesertGasStation.
These scenes are selected before model outcomes. No training or tuning is performed.

From the project root, in the installed WSL model environment:

```bash
PYTHONPATH=.:evaluation/src /opt/loop-detector/ldo-env/bin/python -m tasks.unseen_tartanair.workflow all
```

Individual commands: `install`, `prepare`, `run`, `report`. Completed stages have
hash-checked markers under `evaluation/output/unseen_tartanair`. Frozen source and
configuration hashes prevent accidentally mixing parameter changes into a resumed
experiment. A new protocol/scene selection needs a separate experiment directory.

Datasets and bulky raw artifacts are kept under the WSL roots in `config.yaml`.
Each environment's dated report is copied into the project. The shared evaluation
file handler publishes the combined dated Markdown/JSON report in `evaluation/output`.
Per-environment, per-trajectory and pooled metrics separate candidate/event quality
from individual feature correctness; unknown evidence remains separate throughout.

The original XYZ evaluator and all current reference-geometry gates remain fixed.
Synthetic ground-truth depth is evaluator-only. The two detectors receive the same
grayscale cam0 images and timestamps, not ground truth or IMU measurements.

See [the frozen plan](../../../../.docs/ldo-unseen-tartanair-plan.md).
