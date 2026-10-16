# Dense stereo correspondence for the XYZ evaluator

## Choice

Use the pretrained NVIDIA C-Fast-FoundationStereo official dynamic-resolution
ONNX export. Fast-FoundationStereo is a recent zero-shot stereo model with a
CNN/transformer matching network. This is a modern pretrained option; the
project does not claim it is the best method on every dataset.

Primary sources:
- https://github.com/NVlabs/Fast-FoundationStereo
- https://huggingface.co/nvidia/c-fast-foundationstereo
- https://arxiv.org/abs/2512.11130

## Input and output topology

1. Keep ORB + DBoW2 retrieval and the temporal ORB feature correspondences.
2. Read synchronized raw cam0/cam1 images at each candidate timestamp.
3. Rectify using each camera's true intrinsics, distortion and stereo extrinsics.
4. Feed the rectified pair to the official ONNX stereo graph on the GPU.
   Replicate monochrome into RGB and apply official ImageNet normalization.
   Pad to multiples of 32; crop disparity back to original dimensions.
5. Obtain right-reference disparity by swapping and horizontally reflecting
   both images, then reflecting the result back.
6. Map each original ORB feature into the new rectified coordinate system.
7. Sample its subpixel disparity and find its right-image location along the
   horizontal epipolar line. No separately detected right ORB feature is needed.
8. Require positive finite disparity, valid image coordinates and left-right
   consistency within the configured 1 px limit. Unavailable or occluded
   correspondences do not become negative XYZ evidence.
9. Map the right location back through the rectification map to raw cam1 pixels.
10. Run existing raw calibrated triangulation, covariance propagation, depth,
    parallax and reprojection gates. XYZ remains in original cam0 coordinates.
11. Use reference poses to compare both reconstructed world positions.
12. Under current numerical policy version 8, judge every temporal feature
    correspondence individually. Both observations need reliable depth for an
    XYZ verdict. No temporal RANSAC, image-grid or pair-voting gate changes the
    per-feature verdict. The historical measurements below used older policies.

Stereo preparation version 2 adds a separately masked expanded-field recovery
pass for observations cropped out of the original rectified canvas. The primary
disparity and numerical XYZ/depth thresholds remain unchanged. See
[coverage investigation](stereo-coverage-investigation.md) for the cause,
recorded ablations, matched replay and domain-aware accounting.

Ground truth is used only for admission and final world geometry checks; it is
not fed into neural stereo inference. The pretrained model predicts disparity,
not trusted ground-truth depth. Its mistakes can still affect the evaluator.
Pixel/pose uncertainty remains assumed; it is not learned model confidence.

## Implementation seam

- `dense_stereo.py`: calibration, raw/rectified coordinate conversion, sampling,
  consistency gate, persistent worker ownership and per-frame disk cache.
- `stereo_worker.py`: isolated GPU ONNX inference and structured stdin/stdout.
- `stereo.py`: existing reconstruction and world XYZ calculation.
- `install_fast_stereo.py`: pinned source/model installation and SHA checks.
- `stereo-runtime.lock`: exact dependencies in a dedicated Linux Python 3.12 env.

The worker is initialized once per benchmark, supervised under the benchmark's
process group, and closed in a finally block. Errors fail explicitly. There is
no silent substitution of a classical matcher. `orb_mutual` remains an explicit
configuration option for reproducible historical comparison and synthetic tests.

Each frame's rectified input images, left/right disparity NPZ and cache manifest
are stored in that run's `stereo_correspondences/`. Cache keys include input
image hashes, camera calibration, policy and worker code. NPZ hashes are checked
before reuse. The evaluator records checkpoint and install-manifest hashes.

## Pins and installation

Source commit: 476f4249561f7c79ca707326954f9255643412a6
NVIDIA model revision: 53a84e28a368f37e699776250215fcb450d6a109
ONNX SHA256: 2c79bbb274dc0aef687a8732b987077e9e3aa26ff9dd653141cda48c57dad5d3
Runtime: ONNX Runtime GPU 1.23.2, PyTorch 2.11.0 with CUDA 12.8 libraries.
The official ONNX graph fixes its own architecture and refinement settings;
there are no exposed flags pretending to change those baked graph settings.

Run the installer in WSL Ubuntu from the project root:

```sh
/opt/loop-detector/python-env/bin/python evaluation/src/tasks/feature_matching/xyz/install_fast_stereo.py
```

The published serialized PyTorch checkpoint lacks a normalization setting
required by the pinned latest source. The official ONNX export is used directly
rather than assigning a guessed checkpoint setting.

## Focused validation

The previously reviewed 26-match pair increased from 2 reliable dual-depth
observations to 22. Of those, 21 passed combined XYZ/reprojection gates. Its
coverage was 12.5%, below the unchanged 15% requirement. This is a focused
integration result, not proof of dataset-wide improvement or stereo accuracy.

Tests exercise subpixel sampling, left-right inconsistency, image-border
occlusion and inverse rectification with distorted cameras and nonidentity
rotation. Existing tests cover triangulation, reference transforms, the dynamic
support denominator, report writing and candidate viewer behavior.

## Completed MH_01_easy comparison

Run `evaluation_2026-10-03_17-27-36_043678_ae0ed000` completed all 1,540
ground-truth-eligible candidate checks; 95 candidates were excluded by admission.
All 369 retrieval queries retained identical candidates and scores.

XYZ-only support increased from 9 to 289 candidates under the same version-4
percentage and coverage rules. New XYZ-only groups: 289 supported, 738 with
insufficient evidence, 429 ambiguous, and 84 rejected. These remain diagnostic
evidence decisions, not validated TP/FP accuracy labels.

Combined XYZ and cross-reprojection decisions: 87 supported, 236 suspicious,
and 1,217 inconclusive. Combined and XYZ-only results are different checks.
The reviewed 26-match pair has 22 dual-depth observations, 21 XYZ passes and
12.5% coverage. Its remaining blocker is the unchanged 15% coverage rule.

Verification: 52 unit/integration tests passed; one Linux-native test was skipped
on Windows. The actual GPU benchmark and OpenCV GUI smoke test completed.
