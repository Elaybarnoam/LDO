# ORB-SLAM3 loop rejection diagnosis

Date: 2026-10-02, Asia/Jerusalem. Sequence: EuRoC MH_01_easy, stereo and IMU.

Current status: requested steps 1–3 are complete. The first sections below retain the initial investigation; see **Final diagnostic evidence** for the authoritative instrumentation-6 result and explanation.

## Finding

The native detector rejects the candidates before projection verification or loop correction. This is not a discrepancy introduced by the Python publisher or Markdown renderer. Native JSON events, bridged events, and report counts agree.

| Measurement | First run, instrumentation 2 | Diagnostic run, instrumentation 3 |
| --- | ---: | ---: |
| Tracking frames processed | 3,682 | 3,682 |
| Loop queries | 556 | 572 |
| Eligible queries | 391 | 396 |
| Geometric candidate attempts | 433 | 466 |
| Accepted geometric attempts | 0 | 0 |
| Final accepted loops / inserted constraints | 0 / 0 | 0 / 0 |
| Execution duration | 216.68 s | 213.55 s |

The same pinned upstream revision, settings checksum, dataset and compatibility patch checksum were used. Instrumentation changed; native scheduling and initialization differ between runs. The configured seed does not make native multithread scheduling deterministic.

## Exact failed gates in the diagnostic run

- One attempt had 17 unique BoW map-point matches, below the native threshold of 20.
- 465 attempts passed that gate, but the native Sim3 solver returned `bConverge = false` for all of them.
- No attempt reached initial projection matching, optimized Sim3 inliers, final projection matching, temporal confirmation, or final inertial loop checks.
- BoW match counts across all attempts ranged from 17 to 116; median was 74. Descriptor matches alone did not establish geometrically consistent correspondence.

The pinned native code calls `SetRansacParameters(0.99, 15, 300)` and iterates in batches of 20 until convergence or exhaustion. Its convergence condition is strictly more than 15 geometric inliers. The effective iteration budget is calculated by the native solver and can be below 300. These probes observe the original predicates; they do not change thresholds or correction math.

This establishes the exact failing gate. It does not establish whether each solver failure arose from too few usable 3D correspondences, geometrically inconsistent matches, degenerate geometry, or the finite RANSAC budget. Internal usable-point and best-inlier counts have not been logged.

## Ground-truth context

Diagnostic comparison used `mav0/state_groundtruth_estimate0/data.csv`, selecting the nearest pose within 10 ms of each original camera timestamp. Position distance uses body positions; orientation difference uses the absolute normalized quaternion dot product.

- 456 of 466 candidate pairs had both poses available within that tolerance.
- Candidate position distances: minimum 0.139 m, median 4.466 m, maximum 12.360 m.
- Candidate orientation differences: minimum 10.807 degrees, median 110.948 degrees, maximum 153.608 degrees.
- None met both illustrative thresholds of distance below 1 m and orientation difference below 30 degrees.
- 92 of 396 eligible queries had an earlier *created* keyframe more than 20 s older satisfying those proximity thresholds. Such historical keyframes may already have been culled or connected in the local map.

These are contextual checks, not loop labels or precision/recall measurements. A large space can have visual overlap across several metres or large orientation differences. Nearby poses do not guarantee matching visual content. Native loop selection also excludes candidates whose covisible neighbourhood is already connected to the current keyframe. The current trace does not record those excluded candidates, so it cannot tell us which nearby revisits were excluded by that rule versus absent from BoW retrieval.

## Is zero reasonable?

Zero is consistent with native decisions in two completed runs, and the diagnostic candidates mostly have substantial position or orientation differences. Rejection of those candidates is plausible. The result does not prove that MH_01_easy contains zero genuine revisits, that no useful loop was missed, or that the baseline is ready for an accuracy comparison.

The diagnostic native log also records initialization resets. All 3,682 frames were submitted, but the saved frame trajectory contains 3,592 poses and the keyframe trajectory contains 124 poses. Submitted frames and saved valid poses are different measurements. Initialization variation is another reason to avoid interpreting this single sequence as a stable accuracy benchmark.

## Implemented diagnostics and validation

- Native attempts retain reached gate names, measured values, thresholds, pass/fail and rejection reason.
- The single evaluation output writer aggregates failed gates and measured ranges into JSON and Markdown.
- 21 WSL tests passed, including compiling and exercising the actual C++ logger with rejected and accepted measurements.
- Both retained runs completed with exit code 0 and saved trajectories.
- In the diagnostic run, recorded acceptance agreed with the reached native gate predicates for every attempted pair. Native and bridged rejection counts were independently compared.

## Evidence files

The original reports remain under `evaluation/output/`:

- `evaluation_2026-10-02_15-35-40_119590_51d52397.md`
- `evaluation_2026-10-02_15-48-51_335499_e5be4d10.md`

Each has a JSON report, retained bridged events and a native artifact directory containing the native trace, log, trajectories and build manifest. The Markdown report contains links to its JSON report and bridged events.

## Remaining checks before a model superiority claim

Record retrieval candidates skipped by the connected-neighbour rule, then distinguish lack of retrieval from local-map coverage. If deeper solver diagnosis is needed, log usable 3D correspondence count, best geometric inlier count and effective RANSAC iterations. Independently define valid visual revisits and score recall; compare detectors on the same queries and historical image set. Do not lower verification thresholds merely to produce nonzero loop counts.

## Final diagnostic evidence — steps 1–3 completed

Authoritative report: `evaluation_2026-10-02_16-24-18_182473_0dc6ab83.md`, retained under `evaluation/output/`, alongside JSON, raw bridged events and native artifacts. Instrumentation version 6. Started 16:24:18 and ended 16:27:51, Asia/Jerusalem, on 2026-10-02. Execution duration: 213.54 seconds. All 3,682 input frames were processed; frame trajectory contains 3,678 poses and keyframe trajectory contains 124 poses. Native exit code and runner exit code were zero.

### Step 1: solver internals

An earlier focused instrumentation-4 run had 451 attempts: 3 failed BoW matching, 64 had insufficient usable 3D pairs and 384 exhausted RANSAC without consensus. Maximum best consensus was 2 inliers. This established two distinct solver rejection paths.

The final run had 443 attempts:

| Rejection | Attempts | Evidence |
| --- | ---: | --- |
| Below BoW match threshold | 1 | 17 matches versus required 20 |
| Insufficient usable 3D correspondences | 64 | Fewer than 15 usable pairs; zero RANSAC iterations |
| RANSAC without consensus | 378 | At least 15 usable pairs; actual iterations equal effective iteration limit; best inlier count at most 1 |

Among the 442 attempts reaching the solver, usable pairs ranged from 0 to 40. The native acceptance condition remains strictly more than 15 inliers (16 required). No projection stage, temporal confirmation, final loop gate or loop correction was reached.

### Step 2: retrieval and local-map exclusions

389 eligible queries invoked retrieval; 16 returned no loop candidates. The native vectors returned 789 same-map candidates. All 789 were recorded as selected, independently verified by the native bridge.

- 346 were excluded before geometry because the candidate's covisible neighbourhood was connected to the current keyframe.
- The other 443 entered geometric verification, matching the 443 recorded BoW geometric proposals exactly.
- At the database word-pool stage, 22,364 same-map pair records were directly connected and 15,056 were eligible for shared-word filtering.
- Shared-word filtering retained 1,554 seeds and rejected 13,502. Seed counts and selected-representative counts describe different populations because native covisibility score aggregation can select neighbouring representatives.
- These are stage records, not unique physical loops or false-positive labels.

The instrumentation-5 trial exposed an undercount in selected-representative logging. That reporting defect was corrected in version 6 and guarded with a candidate census check. The same trial also encountered a transient OneDrive Markdown replacement lock; bounded atomic-replacement retries were added, its saved report was recovered, and the final run published without error.

### Step 3: a visually supported historical revisit

The final report embeds two unchanged raw cam0 images:

- Query: `1403636760513555456`, keyframe 556.
- Historical: `1403636599813555456`, keyframe 119.
- Separation: 160.7 seconds.
- Ground-truth body position difference: 0.193 m; orientation difference: 7.39 degrees.
- Independent image matching: 215 unique descriptor matches, 191 fundamental-matrix inliers and 200 homography inliers, with 12.46% inlier bounding-box coverage.
- Visual inspection confirms the same pipework, rack, foreground timber and netting in both frames, with viewpoint and occlusion differences.
- Native selection path: `database_word_pool → direct_connected`. It was excluded because the local map already connected the keyframes, before new loop-candidate geometry.

All 573 traced pairs meeting the illustrative proximity limits (less than 1 m, less than 30 degrees, more than 20 seconds apart) had the same direct-connected exclusion. This is evidence of local coverage for those traced nearby viewpoints. It is not a count of independently labelled visual loops, and does not establish recall over all possible revisits.

### Interpretation and remaining limitation

Zero newly inserted loop constraints is explainable for the observed nearby revisits: native policy already considers them connected locally. The candidates entering geometry did not provide a valid 3D consensus. The examined revisit was neither absent from the word-sharing pool nor accidentally dropped by our publisher.

This validates reporting, candidate exclusions and handling of one genuine visual revisit. It does **not** validate a successful nonlocal loop insertion or establish that every valid loop was found. MH_01_easy in these runs has not exercised the successful new-loop path; a broader benchmark with independently labelled nonlocal revisits is still needed before comparing a transformer or claiming better accuracy. Verification thresholds were not lowered.

Validation: all 25 WSL tests passed; 62,028 native events matched the bridged native event sequence and report counts; selected/returned candidates and geometry-pass/proposal totals matched; insufficient-input and exhausted-budget RANSAC paths were checked against internal counters; both trajectories and complete Markdown publication were verified.
