# Descriptor analysis

This task diagnoses the frozen SuperPoint/LightGlue confidence-0.3 model using
saved TartanAir development descriptors and independently evaluated geometry.
Only datasets with provided ground-truth depth maps and poses are eligible.

```bash
PYTHONPATH=.:evaluation/src OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 \
  /opt/loop-detector/ldo-env/bin/python -m tasks.descriptor_analysis
```

Run from the project root in WSL Ubuntu-24.04. `--output` selects a new artifact
root. An existing root rejects changed source, configuration or manifest inputs.

## Modules

- `ranking.py`: finite normalized cosine similarity, conservative tied ranks,
  forward/reciprocal rank restrictions and one-to-one geometric capacity.
- `workflow.py`: verifies frozen source, descriptors, input images, geometry and
  baseline assignment hashes; audits all 352 original positive development pairs.
- `report.py`: renders the same measurements as readable Markdown.
- `config.yaml`: explicit original inputs, output root and mathematical policy.

Reports pass through the existing singleton FIFO evaluation handler to dated
JSON and Markdown files in `evaluation/output/`. Raw results and per-pair rank
evidence are in `/opt/loop-detector/experiments/descriptor_analysis/v1`.

No ground truth enters inference. Supported edges are evaluator-defined compatible
geometry, not guarantees of unique visual identity. All detected descriptors
compete, including features with unknown reference evidence. Ties within 1e-7
receive the worst tied rank. A feature can be used once in each capacity count.

The 20-correct-match threshold remains a diagnostic. This task performs no model
inference, fine-tuning, promotion, fresh test or SLAM acceptance. OldTownFall is
excluded. Fit and validation data are diagnostic development data for future
choices; they cannot then be advertised as an untouched test.

See [the plan](../../../../.docs/ldo-descriptor-analysis-plan.md) and
[the findings](../../../../.docs/ldo-descriptor-analysis-results.md).
