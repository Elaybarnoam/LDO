# How to evaluate loop-closure correspondences

Visual place recognition asks whether a historical observation is relevant to a
query. Feature evaluation asks whether each reported image correspondence agrees
with independent reference geometry. Operational verification asks whether the
available observations support a relative-pose proposal. LDO records these
separately; success in one does not prove success in the others.

## 1. Understand the three feature verdicts

| Verdict | Meaning under the selected reference policy |
| --- | --- |
| Supported | Judgeable reference evidence passes the fixed geometric criteria |
| Contradicted | Judgeable reference evidence fails those criteria |
| Unknown | Reference evidence is insufficient, invalid or outside the policy's usable scope |

The simulator-depth v2 evaluator samples reference depth under a fixed semantic,
boundary and interpolation policy, and checks XYZ disagreement and symmetric
reprojection. It preserves the original reported feature IDs and assignments.
It does not run the matcher again or recover correspondences using ground truth.
See [the evaluator rules](../../src/loop_eval/tasks/reference_depth_v2/README.md).

Unknown is not another word for incorrect. Report supported/contradicted/unknown
counts, judged precision, judgeable coverage and all-match correctness bounds
together. The complete definitions are in [the method](../method.md) and
[notation](../notation.md).

## 2. Inspect tracked results without a model or dataset

Open [OldTownFall metrics](../../results/matching-oldtown/metrics.json) and
[the study manifest](../../results/matching-oldtown/manifest.json). To independently
calculate the baseline ratios from the tracked counts, run this Python example
from the project root:

```python
import json
from pathlib import Path

row = json.loads(Path("results/matching-oldtown/metrics.json").read_text())["baseline"]
s, c, u = row["supported"], row["contradicted"], row["unknown"]
judged, total = s + c, s + c + u
print("supported / contradicted / unknown:", s, c, u)
print("judged precision:", s / judged if judged else None)
print("judgeable coverage:", judged / total if total else None)
print("all-match bounds:", (s / total, (s + u) / total) if total else None)
```

Expected counts are `40003 100983 9879`, judged precision about `0.283737`,
coverage about `0.934518`, and bounds about `[0.265158, 0.330640]`.
This calculation interprets saved counts. It is not a fresh geometric evaluation
or a confidence interval. Figures can be reproduced using
[the result-reproduction guide](reproduce-results.md).

## 3. Choose the evaluation workflow

| Goal | Entry point | Prerequisites |
| --- | --- | --- |
| Review public saved counts and figures | Reproduction guide | CPU checkout; no raw data |
| Evaluate a completed reference-geometry detector run | `ldo-research reference evaluate` | Full benchmark summary, original assignments, calibrated reference assets and required hashes |
| Run the simulator-depth v2 historical rescore | `ldo-research depth-v2` | Its completed source study, raw feature evidence, depth/semantics and configured asset paths |
| Compare retrieval against independent image-pair labels | `ldo-research compare` | Prepared reference universe, labels and compatible detector traces |

Inspect the interfaces before running an expensive workflow:

```bash
uv run ldo-research reference --help
uv run ldo-research depth-v2 --help
uv run ldo-research compare --help
```

Run numerical reference workflows in the installed Linux/WSL environment. A
completed benchmark can be assessed with:

```bash
uv run ldo-research reference evaluate --config /path/to/reference-config.yaml --results /path/to/completed/summary.json
```

Both paths are placeholders for compatible completed evidence and the applicable
evaluation config. The minimal Python detector export alone is insufficient.
The distinct v2 historical rescore entry point is:

```bash
uv run ldo-research depth-v2 --config /path/to/depth-v2-config.yaml
```

That config's `source`, `asset_root` and `artifact_root` must resolve in the
execution environment. Its fixed numerical thresholds must retain the selected
policy identity. The task may download missing semantic assets. Tracked archive
summaries do not include the raw evidence needed to run either command.

## 4. Preserve independent assessment

Keep references outside the detector. Evaluate all original saved assignments,
including failures; do not preselect only RANSAC survivors or accepted poses.
Retain zero-match pairs, unknown reasons and event identities. Changing a
numerical gate requires a new evaluator/policy identity and a separate result.
Never patch an old hash to force a moved cache to pass.

Image-pair overlap labels and useful-event diagnostics have separate denominators.
Incomplete reference labels withhold overall-recall claims. See
[precision versus event retention](precision-and-event-retention.md),
[protocols](../protocols/README.md), and [reproducibility](../reproducibility.md).
