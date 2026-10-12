# Matching optimization experiment

Runs pretrained feature-matching ablations on identical development pairs, then
tests the frozen selection end to end on fresh OldTownFall trajectories.

From the project root in the installed WSL CUDA environment:

```bash
PYTHONPATH=.:evaluation/src /opt/loop-detector/ldo-env/bin/python -m tasks.matching_optimization.setup
PYTHONPATH=.:evaluation/src /opt/loop-detector/ldo-env/bin/python -m tasks.matching_optimization.workflow all
```

Individual commands: `develop`, `test`, `report`. The setup installs ALIKED and
its compatible matcher into a separate model root, and installs fresh test images,
depth, poses and semantic masks. Original dataset/model roots are preserved.

## Fixed protocol

See `config.yaml` and the [predeclared plan](../../../../.docs/ldo-matching-optimization-plan.md).
Previously examined factory/desert trajectories are explicitly development data.
Each trajectory contributes up to 32 positive, 32 negative and 16 unknown pairs
from the original retrieval union. Pair ordering is deterministic, independent
of optimization outcomes, and shared by every configuration and ORB.

Confidence thresholds, full-depth inference, keypoint count, image resolution and
ALIKED are tested sequentially. Each stage proposes a fit-selected candidate;
validation either promotes that candidate or retains the previous configuration.
Retention gates are relative to the original baseline per scene and overall,
preventing accumulated small losses from escaping the floor. A usable positive
pair has at least 20 independently correct correspondences; this is a measurement
proxy, not a runtime ground-truth decision.

Every run uses production matching adapters. Feature coordinates remain in the
original sensor image even when extraction resizes the image. Descriptor families
and checkpoints are fingerprinted and checked for compatibility. The chosen
settings are written to `ldo/configs/optimized-matching.yaml`; the original
`optimized-confidence.yaml` is preserved.

Independent depth-v2 geometry judges matches and never enters inference. Pair
overlap labels use the existing reference policy. Confidence sweeps postfilter
saved upstream assignments; other changes rerun actual extraction/matching.
Unknown reference evidence remains unknown, including unmapped semantic classes
in scenes without a named sky label.

## Results and resume

Configuration/source hashes, fixed pairs, per-match NPZ evidence, scores, verdicts,
feature caches and source snapshots are under the configured WSL artifact root.
Changed configurations or code cannot be mixed into a resumed experiment. Fresh
test inference requires a completed, frozen development selection.

The existing FIFO report writer produces dated JSON/Markdown in
`evaluation/output`; `evaluation/output/matching-optimization.json` points to the
latest report. The report retains unsuccessful variants and reports raw retrieval
event hits separately from events reached with usable correspondences.

This is an inference optimization experiment, not dedicated transformer training.
One synthetic fresh environment and shared development scenes do not establish
real-world superiority or downstream SLAM improvement.

## Completed experiment

The development selection is SuperPoint / 1024 points / native resolution /
adaptive LightGlue / confidence 0.4. On all three fresh OldTownFall trajectories,
incorrect feature matches fall 17.3% and correct-match retention is 96.7%, while
events meeting the external 20-correct-match diagnostic fall from 13/17 to 12/17.
The lost event has one pair that drops from 20 to 19 correct matches. Retrieval
IDs, ranks and scores remain identical across all 458 queries and 2,107 pairs.

The selected config is an experimental option; retain confidence 0.3 when event
retention is the priority. Test outcomes did not alter the frozen selection or
evaluation gates. See [results and audits](../../../../.docs/ldo-matching-optimization-results.md).
