# Image-pair matcher trial

One predeclared research comparison: official EfficientLoFTR full FP32 against
the frozen confidence-0.3 SuperPoint/LightGlue baseline on 880 identical original
development pairs. Only TartanAir datasets with provided reference depth maps and
camera poses are eligible. No reference data enter model inference.

## Run

From the project root in WSL Ubuntu-24.04:

```bash
PYTHONPATH=.:evaluation/src OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 \
  /opt/loop-detector/efficientloftr-env/bin/python -m tasks.image_pair_matching
```

Use `--output /absolute/new/root` when source/configuration changes. The task
rejects modifications to frozen original inputs and to a reused trial root.

The installed trial environment is isolated at
`/opt/loop-detector/efficientloftr-env`. Its `ldo_base.pth` exposes the original
environment's Torch installation; trial-specific packages take precedence. The
original environment remains unchanged. Required inference versions are recorded
in the model manifest: Torch 2.11.0+cu128, Kornia 0.6.12, einops 0.8.1, loguru
0.7.3, yacs 0.1.8, pytorch-lightning 2.5.5, safetensors 0.8.0 and joblib 1.5.2.
This path-specific environment must be recreated on another machine.

## Official model installation

The installed repository is `/opt/loop-detector/efficientloftr-model/EfficientLoFTR`,
checked out at `07e9c1401e71e9c556b1fda9d86d060af36ba176`. Its official pretrained
checkpoint is `/opt/loop-detector/efficientloftr-model/eloftr_outdoor.ckpt`, from
the Google Drive link in the [upstream repository](https://github.com/zju3dv/EfficientLoFTR).
The upstream source is unmodified.

`setup.py` verifies the Git revision, records checkpoint/source/runtime hashes
and converts only model tensors to `eloftr_outdoor.safetensors`. The original
Lightning checkpoint is read with `weights_only=True` and its sole non-tensor
class, `ModelCheckpoint`, explicitly allowlisted. Runtime inference loads only
the tensor-only file. Source and weights are hash verified before model creation.

The pinned upstream license permits research evaluation without registration.
Retain the upstream license and review its project-use terms before deployment.
This task does not submit registrations or communicate with anyone.

## Replaceable interface

`ldo.matching.image_pairs.ImagePairMatcher.match_images(query, history)` returns
`PixelCorrespondences`: original subpixel query/history coordinates, confidences
and the score definition. Points are pair-dependent and are not cached sparse
feature IDs. The initial adapter is `EfficientLoFTRMatcher`.

Inputs remain native grayscale images with dimensions divisible by 32. Outputs
use the full model's default coarse threshold 0.2, exact endpoint uniqueness and
a confidence-ranked budget of 1,024. There is no resize, integer rounding,
RANSAC, reference-guided filtering or parameter sweep.

## Evaluation and admission

Every original baseline correspondence is re-evaluated in the candidate runtime
and must reproduce its saved verdict. Candidate coordinates then pass through
the same unmodified depth-v2 checker. Zero-output, negative and unknown pairs
remain in the population.

Preliminary gates require, per scene and overall on both splits:

- At least 90% baseline correct-match retention.
- At least 95% baseline usable-positive-pair retention.
- Nondecreasing judged precision and judgeable coverage.
- Fewer incorrect matches overall for each split.

Passing this test only admits full chronological development event replay.
Production promotion additionally requires preservation of individual baseline
usable event IDs and then a frozen untouched-environment test. A failed trial
keeps the baseline and does not advance to a fresh test or silently retune.

Reports use the existing matching-optimization report schema and singleton FIFO
writer. Raw results, parity counts, gating reasons and per-pair NPZ are in the
configured artifact root. This trial is not wired into the production Detector
until it passes the required experiments. See [the plan](../../../../.docs/ldo-image-pair-matching-plan.md).
