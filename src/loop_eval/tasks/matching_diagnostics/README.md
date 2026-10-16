# Matching failure diagnosis

This task explains the frozen confidence-0.3 LDO failures. It does not change model
assignments, use reference data during inference or relax numerical XYZ gates.
Original matching-optimization sources and results remain immutable.

## Run

From the project root in the installed WSL environment:

```bash
PYTHONPATH=.:src/loop_eval /opt/loop-detector/ldo-env/bin/python -m loop_eval.tasks.matching_diagnostics run
PYTHONPATH=.:src/loop_eval /opt/loop-detector/ldo-env/bin/python -m loop_eval.tasks.matching_diagnostics check
```

`run` audits the four weak OldTownFall events and the pre-existing 352 positive
development pairs. It verifies original evidence and semantic hashes, recomputes
the unchanged evaluator's verdicts, and measures maximum one-to-one supported
assignment capacity between existing keypoints. NPZ evidence stores reported
assignments, all keypoints, projected reference positions, supported edges and
an oracle maximum matching.

`check` is a fast red-capable feedback command against the saved diagnosis. It
returns exit code 2 while baseline matching covers 13/17 confirmed events rather
than the all-events diagnostic target. That remains expected until a separately
validated model improvement actually changes the evidence. It does not label
unknown correspondences as failures.

Configuration and provenance are in `config.yaml`; numerical artifacts are under
`/opt/loop-detector/experiments/matching_diagnostics/v1`. Original source hashes,
analysis source/config hashes and per-pair output hashes are retained. If inputs
change, use a new output root with `--output`. Timestamped human Markdown/JSON
reports are published through the existing FIFO evaluation file handler.

## Optional figures

Matplotlib is installed in the current WSL environment. On a new Python setup,
install the `visualization` extra (`uv sync --extra visualization`). Rendering is
separate from numerical analysis:

```bash
PYTHONPATH=.:src/loop_eval /opt/loop-detector/ldo-env/bin/python evaluation/plot_matching_diagnostics.py \
  --results /opt/loop-detector/experiments/matching_diagnostics/v1/results.json \
  --output /opt/loop-detector/experiments/matching_diagnostics/v1/figures
```

Each figure uses the event pair with the greatest reference capacity. The top
panel shows actual model associations; the bottom shows reference-only supported
alternatives. Displayed lines are a labelled subset. Image/evidence/render hashes
and the Matplotlib version are saved in the figure manifest.

## Interpretation

Three weak events have geometrically supported capacity of 20, 37 and 46 matches
but return at most 7, 3 and 8 correct matches. The fourth has capacity 2. Of 363
rejected matches across the weak events, 336 have large residuals. The same
assignment gap appears in 67/352 positive development pairs.

The oracle proves available associations under the fixed evaluator; it cannot
prove visual distinguishability, a unique physical identity or a SLAM constraint.
Small residuals alone do not prove localization error. Unknown depth remains
unknown. OldTownFall is post-test explanation data for this diagnosis and must not
serve as unseen validation of a subsequent fix.

`promotion.assess_promotion` is the guard for future experiments: preserve every
baseline usable event ID per scene, retain at least 90% of correct matches per
scene, reduce incorrect matches and preserve replay/protocol. Evaluate it on
separate complete fit and validation replays. It is not connected to a runtime
model decision and does not alter the historical experiment's selection.

See the [plan](../../../../docs/archive/ldo-matching-diagnostics-plan.md) and
[results with visual examples](../../../../docs/archive/ldo-matching-diagnostics-results.md).
