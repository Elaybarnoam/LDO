# Task: loop image-pair evaluation

Question: does LDO retrieve more genuinely useful revisit pairs than ORB under the same evaluation protocol?

- `config.yaml`: reference dataset, frozen protocol and detector evidence paths.
- `PLAN.md`: end-to-end topology, runtime/evaluation boundaries, shared-verifier contracts and implementation milestones.
- `comparison/`: detector-blind reference preparation, annotation GUI, precision/recall, fixed-pair experiments and sequence aggregation.
- `comparison/README.md`: commands and methodological limitations.

Entry point: `uv run python evaluation/compare.py` with prepare, review, compare, match or aggregate.

The planned shared geometric verifier is not yet implemented. Independent reference labels and held-out evaluation are still required to establish loop-detection superiority. The feature task's external XYZ evaluator is reused without changing its formulas or thresholds.
