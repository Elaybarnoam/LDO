# ORB-SLAM3 diagnostic reporting

## Execution order

1. Run solver diagnostics: count usable 3D pairs, best RANSAC inliers, actual iterations and effective iteration limit.
2. Run candidate selection tracing: shared-word database pool, direct connections, shared-word threshold, selected covisibility representatives, and connected-neighbourhood exclusions before geometry.
3. After native shutdown, validate one historical viewpoint using EuRoC poses and independent image matching; retain both unmodified camera images and publish evidence to the handler.

The native correction and verification thresholds remain unchanged. Native diagnostic logging can change timing and scheduling. Do not compare execution times across instrumentation levels as detector speed measurements.

## Native events

Instrumentation version 6 retains all earlier events and adds:

- `loop_candidate`: original frame timestamps and identities, `candidate_kind`, `selection_stage`, `selection_reason`, and optional measured/required shared-word counts.
- `loop_retrieval`: native output-vector sizes for loop and merge candidates. Native cap is three per kind per query.
- `loop_verified.diagnostics`: usable solver correspondences, best inliers, performed iterations, effective iteration cap and required inliers.
- Detailed rejection reasons: `bow_matches`, `insufficient_3d_correspondences` (fewer than 15 usable pairs), and `ransac_no_consensus` (solver runs but never exceeds 15 inliers).

Candidate stages describe different populations. `shared_words` records database seeds; `top_k` records returned covisibility representatives, which can differ from the seeds. The same pair may produce multiple stage records. These records are not geometric attempts or false positives.

The native bridge checks that selected-record totals equal returned-vector totals for both loop and merge candidates. It also checks that geometry-filter passes equal BoW geometric proposals. Census failures fail the benchmark.

## Historical viewpoint validation

The optional adapter config `diagnostics.validate_revisit: true` enables post-run analysis of the native trace. It selects same-map historical pairs more than 20 seconds apart, with body poses within 1 metre and orientation within 30 degrees. It matches timestamps to nearest EuRoC pose within 10 ms. At most 20 proximity-ranked image pairs are inspected.

An independent image check uses 1,500 ORB features, unique Hamming matches with ratio below 0.75 and distance below 50, and fundamental/homography RANSAC. Evidence requires at least 40 image matches, 25 supported matches, and at least 5% query-image bounding-box coverage. This diagnostic is neither the native 3D solver nor an independent dataset-wide ground-truth evaluator.

The adapter retains source images unchanged in its unique native artifact directory and publishes `revisit_validation`. The single evaluation handler writes the resulting human-readable section, original timestamps, native selection path, images and measured values. Proximity-based selection counts remain separate from independently verified loops. Accuracy fields stay unavailable.

## Output ownership and locks

The orchestrator supervises benchmark processes. The handler's one writer owns shared JSON/Markdown reports and preserves per-benchmark FIFO order. The adapter owns only its unique native artifact directory.

Atomic JSON and Markdown replacement retries transient permission errors with bounded backoff (nine attempts, about 2.75 seconds of waits). Persistent errors still fail output publication. There is no non-atomic fallback, and the pair of files is not a transaction during live updates.

Tests exercise the actual C++ logger, mismatched candidate census rejection, unchanged image exports and explicit absence of accuracy labels, and recovery from transient Markdown replacement locks.
