# LDO optimization: training recipe and independent scene selection

Research date: 2026-10-09. Primary sources only. This document is implementation guidance, not experimental evidence that fine-tuning improves LDO.

## Fixed source versions

- Installed inference LightGlue: `eb42fee2d71449efb0aa5c10549752b5d75384d8` ([source](https://github.com/cvg/LightGlue/blob/eb42fee2d71449efb0aa5c10549752b5d75384d8/lightglue/lightglue.py)).
- Audited official Glue Factory: `2d17e3b3bd7d30f0c828d4c4d3eac4ecefbf283d`, resolved from official GitHub API on research date.
- TartanAir V2 Hugging Face revision: `0d2d145e973832742a2aaa04b7d2ebffc8d82817`.

## 1. A practical matcher adaptation experiment

### Train the final assignment head first

For a small pilot, keep SuperPoint and the LightGlue transformers frozen and adapt the final assignment head only. This is an engineering recommendation for controlling capacity and runtime, not the official full LightGlue training protocol. All training supervision comes from the training environment; deployment still receives only image-derived local features.

The installed inference implementation is differentiable through the assignment head. Its public output omits the assignment matrix. Capture the existing final assignment module output through a PyTorch forward hook; do not recreate the transformer or modify third-party source. Disable early stopping and pruning so every sample reaches that head. The `MatchAssignment.forward` return is `(log_assignment, similarity)`. Its final row and column encode unmatched features. ([Pinned assignment implementation](https://github.com/cvg/LightGlue/blob/eb42fee2d71449efb0aa5c10549752b5d75384d8/lightglue/lightglue.py#L236-L277), [pinned forward implementation](https://github.com/cvg/LightGlue/blob/eb42fee2d71449efb0aa5c10549752b5d75384d8/lightglue/lightglue.py#L452-L589))

```python
matcher = LightGlue(
    features="superpoint", depth_confidence=-1,
    width_confidence=-1, flash=False, mp=False,
).to(device).train()
for parameter in matcher.parameters():
    parameter.requires_grad_(False)
for parameter in matcher.log_assignment[-1].parameters():
    parameter.requires_grad_(True)

captured = {}
def capture_assignment(module, inputs, output):
    captured["log_assignment"] = output[0]
handle = matcher.log_assignment[-1].register_forward_hook(capture_assignment)

# Cached image0/image1 dictionaries: BxNx2 keypoints,
# BxNx256 descriptors, Bx2 image_size (width,height).
# Cached descriptors are detached; no extractor training.
matcher({"image0": image0, "image1": image1})
la = captured.pop("log_assignment")
# Compute the masked loss below, backward, optimizer.step().
# Remove the hook in finally; save the full state dict and provenance.
```

Use AdamW, a predeclared low learning rate, fixed seed, deterministic ordering, and a fixed 100-300-update budget for the initial test. Check loss and gradient finiteness. Check checkpoint reload parity before evaluating it. Cap cached features deterministically to 256 if compute is limiting; compare the untrained model with the same cap, then measure full-1024 deployment separately. Do not present a feature-cap change as learned improvement.

### Loss and masking

Official Glue Factory uses `gt_assignment` (B,M,N boolean), `gt_matches0` (B,M integer), and `gt_matches1` (B,N integer). Matched features contain their partner index, `-1` means definitely unmatched, and `-2` means ignored. Its balanced NLL has one positive-assignment term and one dustbin term. Unknowns contribute neither. ([Pinned loss](https://github.com/cvg/glue-factory/blob/2d17e3b3bd7d30f0c828d4c4d3eac4ecefbf283d/gluefactory/models/utils/losses.py), [label sentinels](https://github.com/cvg/glue-factory/blob/2d17e3b3bd7d30f0c828d4c4d3eac4ecefbf283d/gluefactory/geometry/gt_generation.py#L8-L96))

For each batch, with M/N the non-dustbin sizes:

```text
L_positive = mean(-LA[i,j] for each positive GT assignment)
L_negative = sum(-LA[i,N] for GT0[i] == -1,
                 -LA[M,j] for GT1[j] == -1) / max(negative count,1)
L = 0.5 * L_positive + 0.5 * L_negative
```

Use a zero differentiable positive term if there are no positives; skip examples with no supervision at all. Clamp denominators, not unknown labels. Do not train every erroneous model-reported correspondence as an unmatched feature: that feature may have another correct partner.

Create independent supervision across **all cached feature pairs**, not only matches the pretrained model already predicts. Official depth supervision finds mutually nearest reprojections, requires symmetric error below 3 pixels for positives, uses a wider 5-pixel negative margin, and ignores ambiguous cases. Preserve our reference-depth quality, visibility, and static-scene assumptions rather than lowering evaluator gates to manufacture labels. Keep invalid/ambiguous reference geometry ignored. ([Pinned GT generator](https://github.com/cvg/glue-factory/blob/2d17e3b3bd7d30f0c828d4c4d3eac4ecefbf283d/gluefactory/geometry/gt_generation.py#L11-L96))

### Checkpoint deployment

Because adaptation uses the installed inference class itself, save `matcher.state_dict()` and load it into the same pinned class with `strict=True`. Record architecture, feature extractor, adaptation mode, training seed, source/data hashes, optimization steps, and SHA256 of the checkpoint. Keep early stopping disabled: an adapted final head is otherwise bypassed when a pretrained intermediate head exits early. Keep the pretrained checkpoint immutable for comparison.

This final-head experiment is **not** full official LightGlue training. Full training supervises assignment outputs at all transformer layers and trains token confidence. It has a distinct training forward output containing layerwise refined descriptors and `log_assignment`. The official factory method is `pred = model(data); losses, metrics = model.loss(pred,data); losses["total"].mean().backward()`. Inputs use `keypoints0/1`, `descriptors0/1`, and `view0/1.image_size`. ([Pinned training matcher](https://github.com/cvg/glue-factory/blob/2d17e3b3bd7d30f0c828d4c4d3eac4ecefbf283d/gluefactory/models/matchers/lightglue.py#L380-L577))

The official configuration supports cached features, frozen SuperPoint, 3/5-pixel GT thresholds, and matcher-only training. It is the appropriate next step if the small adaptation demonstrates value. Do not silently substitute the factory implementation without state-key and forward-parity tests. ([Official configuration](https://github.com/cvg/glue-factory/blob/2d17e3b3bd7d30f0c828d4c4d3eac4ecefbf283d/gluefactory/configs/superpoint%2Blightglue_megadepth.yaml))

### Executed API sanity check

I executed the hook recipe against the installed WSL LightGlue package with a two-layer untrained instance and synthetic cached inputs (32 and 24 features). The captured assignment had shape `(1,33,25)` and `requires_grad=True`. A positive-plus-dustbin loss produced finite, nonzero gradients for all four final-head parameter tensors (`matchability.weight/bias`, `final_proj.weight/bias`). This verifies the adaptation plumbing only; it is not a trained-model result.

## 2. Independent environments selected by archive size

I queried every environment's `Data_easy` directory from the fixed official dataset revision, before observing detector results. These are the two smallest environments with names indicating different scene geometry from the already-used TinyHouse scene. This is a practical independent-environment pilot, not certification that scenes contain no shared assets.

| Environment / role | Left image bytes | Left depth bytes | IMU bytes | Left-only total |
|---|---:|---:|---:|---:|
| RetroOffice / training | 625,680,128 | 179,933,201 | 4,157,645 | 809,770,974 |
| CountryHouse / untouched test | 1,134,659,260 | 360,068,455 | 8,978,224 | 1,503,705,939 |

Sources: [RetroOffice official API](https://huggingface.co/api/datasets/theairlabcmu/tartanair2/tree/0d2d145e973832742a2aaa04b7d2ebffc8d82817/RetroOffice/Data_easy?recursive=false&limit=1000), [CountryHouse official API](https://huggingface.co/api/datasets/theairlabcmu/tartanair2/tree/0d2d145e973832742a2aaa04b7d2ebffc8d82817/CountryHouse/Data_easy?recursive=false&limit=1000).

If the existing adapter still requires both cameras, RetroOffice right images add 624,679,179 bytes and right depth adds 180,356,772 bytes. CountryHouse right images add 1,142,279,674 bytes and right depth adds 361,983,709 bytes. The direct-reference-only evaluator needs neither right modality: both temporal observations are left images with their own reference depth and pose. IMU archive contains trajectories/reference poses in the already-inspected TinyHouse release; verify that fact for each new archive before using it. Sources are the two pinned API endpoints above.

TinyHouseNight is smaller (left-only 544,998,301 bytes), but its day/night name indicates the same scene. Do not use it as independent scene evidence. ([Official TinyHouseNight API](https://huggingface.co/api/datasets/theairlabcmu/tartanair2/tree/0d2d145e973832742a2aaa04b7d2ebffc8d82817/ArchVizTinyHouseNight/Data_easy?recursive=false&limit=1000))

## 3. Freeze an interpretable evaluation protocol

- Training: RetroOffice only. Use reference geometry to sample overlapping pairs and appearance-confusing non-overlaps without selecting based on final test performance.
- Development: TinyHouseDay is already observed; use it for match/confidence policy and checkpoint selection, explicitly disclosing repeated use.
- Test: CountryHouse, untouched until confidence policy and checkpoint are frozen. Evaluate once; record failures and do not retune against them.
- Compare baseline, confidence-only, candidate-policy, and learned-head variants on exactly the same frozen image inputs and eligible pair universe.
- Report supported/contradicted/unknown matches, retained supported count, candidate precision/recall, and unknown coverage separately. Improvement in judged precision caused only by dropping many correct matches is not unqualified improvement.
- Do not equate correct feature correspondence with correct place detection or accurate relative-pose estimation.

Pretrained upstream training overlap remains unaudited. Scene-level separation protects this experiment's adaptation split; it does not establish that the pretrained models have never seen these synthetic environments.
