# Evaluation benchmark plan

Status: requirements recorded; execution deferred at the user's request.

Progress update: EuRoC MAV has been installed under `evaluation/datasets/euroc/`. All eleven ASL sequences passed installation validation. See [dataset installation notes](euroc-dataset.md) for provenance and integrity checks. The runner, orchestrator, IPC publisher, FIFO file handler, and timestamped reporting are implemented. Native baseline adapters, independent loop labels, development/test splitting, and labelled metrics remain pending; the configured benchmark list is empty.

This file is the shared plan for the future evaluation benchmark directory. The current task only creates this document. Dataset downloads, installations, baseline setup, dataset splitting, and benchmark implementation will begin in a later work phase.

## Objective

Evaluate whether our transformer loop detector finds more genuine loop closures with fewer false proposals when integrated into existing visual–inertial SLAM implementations.

Compare each SLAM implementation's original detector against the same implementation using our component. Preserve the existing geometric verification and loop correction wherever the integration permits, and record any changes required at that boundary. A comparison across different SLAM systems alone cannot isolate our detector's contribution.

The evaluation must report loop detection performance directly, as well as whether the additional detections help the downstream SLAM system.

## Dataset to identify

The user remembers a public dataset with camera and IMU streams whose name starts with “EU”, previously discussed in other chats. The likely name is **EuRoC MAV**, but this is an unverified recollection in this plan.

When work begins:

1. Search accessible previous chats to recover the exact dataset, sequence names, and earlier setup decisions.
2. Confirm dataset contents, ground truth, calibration, timestamps, licenses, and official download locations using primary sources.
3. Check whether the selected sequences contain enough evaluable revisits. A trajectory benchmark is not automatically a complete loop-detection benchmark.
4. Choose additional public visual–IMU datasets if needed to evaluate different environments, appearance changes, and revisit patterns. Do not treat one dataset as evidence of general performance.

## Held-out evaluation and distribution shift

Reserve a dedicated evaluation subset before tuning thresholds or fine-tuning a model. Split by complete sequence, session, or environment as appropriate; adjacent frames from the same trajectory must not leak across tuning and evaluation sets.

Record the pretrained model's known training datasets. Distinguish “held out from our tuning” from “outside the pretrained model's training distribution”. Declare distribution shift based on actual environment, sensor, motion, or appearance differences. A random seed alone does not make a test out of distribution.

Use fixed, recorded seeds for reproducible sampling and stochastic operations. Record exact sequence lists and checksums in a split manifest. Keep the final evaluation split frozen; use a separate development split for integration, parameter selection, and failure analysis. Preserve the complete source trajectories when selecting subsets so camera–IMU synchronization and motion continuity remain valid.

## Existing SLAM baselines

Set up several public SLAM implementations using their released code, dependencies, and supported dataset configurations. Select the final list after verifying current implementations and integration support.

Initial candidates to investigate are ORB-SLAM3, VINS-Fusion, and OKVIS2. These names are research candidates, not a verified list of current state-of-the-art systems. Confirm that each selected configuration actually supports visual–IMU estimation and an observable loop detector. Include a recent reproducible system if it meets those requirements.

For every baseline, record the repository, exact revision, configuration, sensor mode, camera calibration, build environment, and original loop-detection method. Establish a successful original run before replacing its detector. Prefer supported stereo–IMU configurations where compatible with the dataset; document any different sensor inputs used by other baselines.

Required comparison modes per compatible baseline:

| Mode | Purpose |
|---|---|
| Original detector | Establish the released system's detection and SLAM performance. |
| Our detector with pretrained weights | Measure our component's contribution without benchmark-specific model training. |
| Our detector with optional sequence/IMU checks disabled | Isolate the contribution of those deterministic checks. |

Further variants are optional and should answer a concrete question. If fine-tuning is later introduced, report it separately with its training data and split provenance.

## Ground truth for loop opportunities

Define a genuine loop opportunity before counting detections. Specify temporal separation, spatial distance, orientation/visibility or view-overlap criteria, and grouping into revisit events. Position proximity alone can label non-overlapping camera views as matches; reused visual geometry must be considered.

Use independent dataset ground truth where available, supplemented by an explicit, reproducible visibility/overlap annotation method. The existing SLAM verifier's acceptance is a useful downstream outcome, but must not serve as the sole ground-truth label.

Store both pair-level labels and event-level labels. Repeated proposals during one revisit must not inflate the number of distinct loop events detected. Define the event grouping and matching policy before running the comparison. Document ambiguous and unlabelled cases rather than silently counting them as false positives.

## Measurements

Log three boundaries separately: detector proposal, existing geometric verifier acceptance, and successful addition of a loop constraint. This distinguishes a detector failure from a downstream rejection or integration failure.

| Measurement | Meaning |
|---|---|
| Proposal count | Total pairs emitted by the detector. |
| True positives (TP) | Proposals or revisit events correctly matched to independent ground truth. |
| False positives (FP) | Proposals or events labelled incorrect by ground truth. |
| False negatives (FN) | Eligible ground-truth pairs or events missed by the detector, under the declared matching policy. |
| Precision | TP / (TP + FP). |
| Recall | TP / (TP + FN). |
| F1 | Harmonic mean of precision and recall. |
| False proposals per hour | FP normalized by the evaluated recording duration. |
| Distinct loop events detected | Number of genuine revisit events recovered, with duplicates grouped. |
| Detection delay | Time from an eligible revisit to its first correct proposal. |
| Processing latency | Time spent on retrieval, pair scoring, and the full detection path; report median and tail latency. |
| Geometric acceptance count | Number of proposals accepted by the existing geometric verifier. |
| Accepted false loops | Independently incorrect matches that pass verification and enter the graph. |
| Trajectory error and failures | Dataset-appropriate absolute/relative trajectory error, tracking failures, and completed runs. |
| Resource cost | Peak memory, descriptor/index storage, and hardware used. |

Report pair and event metrics separately, with raw counts per sequence and aggregate summaries. Do not calculate a true-negative rate unless the evaluated negative-pair universe is explicitly defined. Mark metrics with zero denominators as undefined.

Sweep detector thresholds on development data to compare recall at the same false-proposal rate or precision. Lock operating points before final evaluation. Compare latency and resource budgets as well as accuracy. State uncertainty using suitable independent units such as sequences or revisit events; adjacent frames are not independent samples.

## Proposed evaluation directory

Create this structure during the implementation phase, not during this documentation task:

```text
evaluation/
  README.md             # Setup, execution, and interpretation
  datasets/             # Download manifests and local paths; large data location configurable
  splits/               # Frozen development/test manifests and seeds
  baselines/            # Pinned implementation setup and original configurations
  adapters/             # Keyframe inputs, detector substitution, and event logging
  configs/              # Dataset, model, threshold, and runtime configurations
  ground_truth/         # Loop definitions, labels, and annotation provenance
  runners/              # Reproducible original-versus-component runs
  metrics/              # Pair/event matching and metric computation
  results/              # Run manifests, logs, summaries, and plots
```

Each run manifest must identify dataset/split, baseline revision, detector weights, configuration, seed, hardware, timing conventions, and any unsuccessful sequences. Avoid committing downloaded datasets and generated large artifacts to source control.

## Order of future work

1. Recover the earlier chat context and verify the dataset identity.
2. Verify dataset and baseline choices, dependencies, and execution environment.
3. Download and validate source data, then freeze development/evaluation manifests.
4. Prepare the evaluation directory and log format.
5. Run original SLAM baselines and establish loop ground-truth annotations.
6. Connect our pretrained detector at the documented interface.
7. Tune on development data, freeze settings, and run the held-out comparisons.
8. Report detection counts, false positives, missed loops, timing, and downstream SLAM outcomes with reproducible run manifests.
