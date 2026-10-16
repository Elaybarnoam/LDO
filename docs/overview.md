# Scope and research questions

## Problem

A visual localization system can revisit previously observed places. Retrieving
an image that looks similar is only the first step: temporal neighbors must be
excluded, repetitive appearance can yield incorrect assignments, available depth
can be insufficient, and a geometrically accepted transform can still represent
an incorrect constraint. Evaluating each stage requires independent evidence.

LDO takes chronological camera frames and produces ranked historical candidates,
local observations, and correspondence assignments. The current research baseline
uses frozen MegaLoc, SuperPoint, and LightGlue weights at confidence 0.3. Optional
image-only stereo and PnP verification produce query-to-history relative-pose
proposals. Offline reference evaluators assess features, candidate overlap,
confirmed event runs, and pose errors independently.

Neither current detector consumes IMU. The repository's distribution identifier
`visual-imu-loop-detector` is retained for compatibility and does not describe
implemented inertial fusion. Native ORB-SLAM3 instrumentation exists as a separate
benchmark; the component ORB + DBoW2 comparison is not the full SLAM acceptance
pipeline. Current LDO studies do not establish downstream trajectory improvement.

## Contributions and evidence

| Repository contribution | Implementation | Evidence | Limitation |
| --- | --- | --- | --- |
| Causal, replaceable visual proposal pipeline | `ldo.Detector`, encoder/matching/policy interfaces | Chronology/representation tests and frozen replay reports | Learned backbones and matchers are upstream methods |
| Observation-only shared metric verification | `loop_verification`, `stereo_observations` | Synthetic pose tests and separate full-pipeline pilot | Acceptance gates are provisional and require independent assessment |
| Auditable independent correspondence assessment | `loop_eval.tasks.reference_geometry`, `reference_depth_v2` | Saved assignments, supported/contradicted/unknown verdicts, rescore records | Simulator evidence is incomplete and policy-dependent |
| Sequential selection and failure analysis | Matching/descriptor/image-pair tasks | Successful and failed promotions; event identities and losses | Inspected scenes cannot repeatedly serve as fresh tests |

These are software and evaluation contributions. This repository does not claim a
new pretrained architecture, a peer-reviewed result, or a theorem of superiority.

## Questions addressed

1. Under the same causal replay and independent overlap policy, which confirmed
   opportunities do LDO and ORB + DBoW2 retrieve?
2. Can matching settings reduce contradicted assignments while retaining
   supported assignments and specific useful events?
3. What distinguishes retrieval failure, assignment ambiguity, insufficient
   reference evidence, and operational pose-verification failure?

See the [study registry](../results/index.json), [method](method.md), and
[limitations](limitations.md) for the populations and qualifications behind each answer.
