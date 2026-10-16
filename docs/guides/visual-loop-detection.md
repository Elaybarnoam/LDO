# Visual loop detection with MegaLoc and LightGlue

LDO combines visual place recognition with local feature matching. MegaLoc ranks
eligible historical images; SuperPoint and LightGlue produce correspondences in
original camera pixels. A proposal is inspectable evidence for a possible revisit,
not automatically an accepted SLAM correction. The current detector is camera-only.

## 1. Check the installed interface on CPU

From a checkout with Python 3.11 and uv:

```bash
uv sync --locked
uv run ldo-research doctor
uv run ldo-research smoke --output artifacts/smoke.json
```

Expected eligible-history counts: `[0, 0, 1, 2]`. The last query returns candidate
IDs `0` and `1`, with two assignments per candidate. The JSON reports
`mode: synthetic_cpu_smoke` and `research_result: false`. This exercises the
production detector with deterministic synthetic adapters, without model weights.
See [the minimal replay](../../examples/minimal_replay/README.md).

## 2. Prepare the learned-model runtime

The retained baseline is
[optimized-confidence.yaml](../../configs/models/optimized-confidence.yaml):
MegaLoc, SuperPoint + LightGlue, 1,024 keypoints, confidence 0.3, top-k 5 and a
5-second temporal exclusion. Confidence 0.4 remains experimental.

Learned experiments use the Linux/WSL CUDA profile. Inside WSL, after checking
the upstream model and weight terms, follow these installation commands:

```bash
uv sync --locked --extra ldo
uv run ldo-research configure --runtime-root /home/you/ldo-runtime --output artifacts/local-configs
export LDO_CONFIG_ROOT="$PWD/artifacts/local-configs"
export LDO_MODEL_ROOT=/home/you/ldo-runtime/ldo-models
uv run python -m ldo.install --root "$LDO_MODEL_ROOT"
uv run ldo-research doctor --model-root "$LDO_MODEL_ROOT" --probe-cuda
```

Replace `/home/you/ldo-runtime` with your absolute runtime directory. Generate the
profile once: an existing destination is refused. Installation downloads pinned
model sources and checkpoints; the driver probe does not certify PyTorch runtime
compatibility. Configured CUDA inference fails rather than silently using CPU.
See [installation](../installation.md) and [licensing](../licensing.md).

## 3. Process your chronological images

The following Python integration example assumes the learned runtime is installed.
Replace both image paths with your own cam0 images and use their actual timestamps
in integer nanoseconds. The example's two timestamps illustrate a 6-second gap;
they are not an acquisition recipe or evidence of a revisit.

```python
from pathlib import Path

from ldo.configuration import build_detector, load_config
from ldo.contracts import KeyframeInput
from ldo.evidence import EvidenceWriter
from loop_eval.paths import configuration_path

config = load_config(configuration_path("configs/models/optimized-confidence.yaml"))
frames = [
    KeyframeInput("first", 0, Path("/data/trajectory/first.png")),
    KeyframeInput("later", 6_000_000_000, Path("/data/trajectory/later.png")),
]
detector, manifest = build_detector(config)
try:
    # Use a new output directory for each attempt; existing evidence is refused.
    writer = EvidenceWriter(Path("artifacts/my-visual-replay"), manifest)
    for frame in frames:
        batch = detector.process_keyframe(frame)
        writer.append(batch)
        print(frame.keyframe_id, batch.eligible_history_count)
        for candidate in batch.candidates:
            print(
                candidate.historical.keyframe_id,
                candidate.rank,
                candidate.retrieval_score,
                len(candidate.matches.indices),
            )
    writer.finalize()
finally:
    detector.close()
```

Save the adapted example as `artifacts/my_visual_replay.py` and run it in the
configured environment with `uv run python artifacts/my_visual_replay.py`.
Inputs must have strictly increasing timestamps, distinct IDs, existing images
and a consistent session. Querying happens before insertion. A failed inference
instance must be replaced; do not continue it. A failed run may leave partial
files; `manifest.json` is written only after successful completion in this example.

`EvidenceWriter` saves feature pixels, original assignment indices/scores, image
hashes and model provenance. This minimal feature export is not a complete
benchmark summary accepted by `reference evaluate`. Use the established benchmark
workflow for numerical comparison, calibration/reference linkage and full run records.

## 4. Interpret the proposals

- Retrieval cosine similarity ranks candidates; it is not a loop probability.
- Matcher confidence describes assignment scoring, not calibrated loop correctness.
- Zero matches is a valid outcome. Keep such pairs in evaluation totals.
- Independent depth/pose/semantic reference data belong in the offline evaluator.
- Optional stereo/PnP verification is a separate observation-only component;
  this minimal example does not invoke it or produce an accepted pose constraint.

Continue with [correspondence evaluation](evaluate-correspondences.md),
[the mathematical method](../method.md), or
[a first contribution](https://github.com/Elaybarnoam/LDO/contribute).
