# Task: feature correspondence evaluation

Question: which reported ORB or LDO feature correspondences have sufficient stereo evidence, and do their reference-world XYZ estimates agree?

- `xyz/`: stereo preparation, uncertainty, numerical XYZ verdicts, saved evidence and coverage analysis.
- `xyz/config.yaml`: unchanged numerical evaluation policy.
- `PLAN.md`: task responsibilities, maintenance rules and validation contract.
- `viewer/`: feature-by-feature review and evidence explanations.

Outputs are supported, contradicted and untestable observations. They do not count accepted loops or establish loop recall.

Entry point: `uv run python evaluation/view_suspicious.py`.

Coverage analysis from `evaluation/src`: `python -m tasks.feature_matching.xyz.coverage_analysis --checks DIR --output FILE.json`.
