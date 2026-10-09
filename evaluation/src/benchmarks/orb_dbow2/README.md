# ORB + DBoW2 image retrieval baseline

This benchmark isolates image retrieval from the existing SLAM system. It uses
the ORB-SLAM3 `ORBextractor.cc`, `ORBVocabulary` typedef, bundled DBoW2 implementation,
and published vocabulary from pinned revision
`4452a3c4ab75b1cde34e5505a36ec3f9edcdc4c4`.

It is **not the full ORB-SLAM3 loop detector**. It does not reproduce native
keyframe selection, common-word gates, covisibility score accumulation, connected
map filtering, temporal confirmation, geometric verification, or correction.

## Process

`runner → orchestrator → inherited Benchmark adapter → native image retrieval`

`native ranked queries → inherited publisher → stdout IPC → orchestrator → file-handler FIFO → Markdown + JSON`

The adapter runs cam0 chronologically at 2 Hz, with 20 seconds of temporal
exclusion and top 5 positive-score candidates. Sampling uses a fixed time grid:
the first available image at or after each grid time. Each image is queried
before insertion; ties use the oldest timestamp first. The exact replay is
retained as `replay.tsv` and hashed. Original dataset files are untouched.

Every eligible BoW vector is scored with `vocabulary.score`. This exact scan is
simple and reproducible; it is not an optimized inverted-index implementation.
Similarity scores are not calibrated probabilities. Repeated candidates are
image pairs, not unique physical revisits.

## Build and run (WSL)

The installed source, DBoW2 library, vocabulary and Linux dataset cache from the
existing ORB-SLAM3 setup are prerequisites. The benchmark runtime links OpenCV
and DBoW2, **not** `libORB_SLAM3`, g2o or Pangolin. A separate reference executable
links upstream SLAM methods only for verification.

From the project root:

```sh
/opt/loop-detector/python-env/bin/python evaluation/src/benchmarks/orb_dbow2/build.py
cd evaluation/src
/opt/loop-detector/python-env/bin/python -m benchmarks.orb_dbow2.verify
cd ../..
/opt/loop-detector/python-env/bin/python evaluation/src/runner.py
```

From Windows, the existing `uv run python evaluation/run_wsl.py` launcher runs
the evaluation inside WSL.

Configuration is in `config.yaml`; the active case is selected by
`evaluation/src/config.yaml`. The old full-SLAM adapter and its reports remain
available but are no longer the active default case.

## Upstream parity

EuRoC cam0 preprocessing reproduces `Settings` rectification and
`System::TrackStereo` remapping. Pinhole parameters and transforms use upstream
float conversions, and extraction uses overlap limits `{0, 0}`.

The pinned `Settings::camera2DistortionCoef` accessor returns the camera1
coefficient storage. We deliberately reproduce that upstream behavior for
parity; this is not a newly chosen calibration policy.

`verify.py` compares two real revisit images against actual upstream
`Settings`, `Frame::ExtractORB`, `Frame::ComputeBoW` and `vocabulary.score`.
Rectified PNG bytes, descriptor bytes and BoW word/weight files must match
exactly. The build runs this as a required gate and saves `verification.json` in the Linux build directory. The adapter checks the verified binary hash and retains the receipt in its run artifacts. This proves
parity on the checked pair; it does not prove equivalence to all full-SLAM
candidate-selection behavior.

## Results and limitations

The singleton file handler writes timestamped `.md` and `.json` reports with
queries, eligible queries, empty eligible results, candidate records, timing,
errors and exit status. Every query retains ranked timestamps and scores in
`events.jsonl` and the adapter's native `retrieval.jsonl`.

The prior visually inspected revisit is looked up using the nearest uniform
samples and displayed as a qualitative diagnostic. It is not a positive label
for the sampled pair. IMU remains in the dataset but is not consumed by this
visual retrieval baseline.

The enabled `candidate_evaluation` section runs a separate offline ORB/stereo
reference-world geometry checker after native retrieval. It reconstructs XYZ
from cam0/cam1 independently at both timestamps, transforms both estimates into
the reference world frame, and checks covariance-weighted XYZ error and
bidirectional reprojection. Invalid or uncertain depth remains inconclusive.
The previous 2D checks are retained as separate evidence. It reports overlap-supported,
suspicious and inconclusive evidence, with review images. It does not use
DBoW2 scores for its decisions; correspondences use the exported native ORB features. Its policy is configured in
`evaluation/src/tasks/feature_matching/xyz/config.yaml`; artifacts are retained
under each run's `candidate_checks/`; complete per-landmark XYZ and errors are
retained in `pairs.jsonl`. Assumed pixel and reference-pose uncertainty is
configured explicitly; reconstructed landmark XYZ is not ground-truth XYZ.
Native retrieval timings exclude this
offline checking cost. See `.docs/independent-candidate-evaluation.md`.

TP/FP/FN, precision, recall and unique detected-loop counts remain unavailable
until independent visual-overlap labels, a frozen split, and event matching
rules are implemented. No transformer comparison or OOD claim is made yet.

Reused ORB-SLAM3/DBoW2 components are GPL-3.0-or-later; preserve their upstream
license notices when distributing this native implementation.

The active stereo backend uses pretrained Fast-FoundationStereo dense
correspondences at the exported ORB locations. See `.docs/dense-stereo-evaluation.md`
for the isolated GPU runtime, pinned model and rectification topology.
