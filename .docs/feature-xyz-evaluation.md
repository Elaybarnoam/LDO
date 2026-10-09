# Feature correspondence XYZ evaluation - policy version 8

## Boundary and flow

DBoW2 candidate image pair -> mutual Hamming matching of exported upstream ORB descriptors -> every reported feature correspondence -> prepared stereo observations -> numerical XYZ checker -> one feature verdict -> FIFO writer/report and feature viewer.

No temporal RANSAC or image-grid coverage filters precede this evaluation. Homography and reference epipolar diagnostics remain separate; they do not filter correspondences or override feature verdicts.

`xyz.FeatureObservation` contains timestamp, feature ID, pixel coordinates, camera XYZ, depth covariance, reference camera pose and depth failure reason. `xyz.check_correspondence(query, historical, policy)` performs no image I/O, feature extraction or matching. `StereoGeometry` prepares the observations using synchronized stereo, cached depth and reference poses.

## Verdicts

- Supported: both observations have reliable stereo depth, valid uncertainty and poses; squared covariance-weighted world XYZ discrepancy <= 11.345.
- Contradicted: both observations are testable but the discrepancy exceeds the threshold. This is evidence of a suspected false feature correspondence, not a definitive loop false positive.
- Untestable: missing/unreliable depth, missing pose or invalid numerical uncertainty. Each side retains its reason; missing depth is never counted as a contradiction.

Reprojection is auxiliary numerical evidence. It does not alter the XYZ-only verdict. Each result saves IDs, pixel coordinates, camera/world XYZ when available, reference poses, uncertainty, Mahalanobis score, verdict/reason, Hamming distance, reprojection diagnostics and numerical-check duration.

## Accounting and timing

Stereo preparation version 2 retains the original disparity projection and
recovers observations outside that projection on an expanded rectified canvas.
Both projection domains explicitly mask sensor padding. Numerical XYZ and
reconstruction gates remain unchanged; the preparation change has its own
provenance. See [coverage investigation](stereo-coverage-investigation.md).

Every admitted image pair saves all feature results in candidate_checks/pairs.jsonl. The publisher transmits bounded per-pair feature counts, timings and evidence-file location. The existing singleton FIFO handler validates per-pair counts and reconciles final totals before writing JSON/Markdown.

Reported = supported + contradicted + untestable.
Testable = supported + contradicted.
Contradiction rate = contradicted / testable (null for zero testable).
Evaluation coverage = testable / reported (null for zero reported).

Counts are correspondence observations across pairs, not unique environment landmarks. Ground-truth admission still excludes image pairs without both valid reference poses. Empty-match image pairs are reported with zero counts.

Each result also publishes a bounded coverage breakdown: exclusive joint
query/history failure reasons, per-side reasons, which side lacks depth, and
verdict counts within the primary rectified domain versus the additional raw
field of view. No match is removed from the total to increase coverage. The
singleton writer reconciles these counts against every pair and the final
summary. The coverage analysis utility separately audits unique timestamp/
feature observations and evidence integrity.

Stereo preparation/reprojection and pure XYZ checking are timed separately. Shared stereo caches prevent attributing preparation costs precisely to a bad feature. These timings do not claim downstream SLAM work avoided or wasted.

## Viewer

Four feature filters: all, supported, contradicted, untestable. Button counts are feature counts. A/D, arrow keys, Previous/Next and brackets navigate one feature at a time; crossing the last feature advances to the next image pair and backward reverses this order. Empty-match image pairs are omitted from feature pagination only. Ends clamp instead of wrapping.

Green = supported, red = contradicted, cyan = untestable. Reprojection is shown numerically instead of changing the primary feature color. The selected feature is highlighted; L optionally shows all lines in the active image/filter. Clicking a feature selects it. Copy saves its verdict, reasons, preparation and numerical evidence. Legacy reports retain their original viewer behavior.

## Verification

Known equal world points under different camera poses; wrong world point; missing depth; invalid covariance; every ORB pair reaches preparation without fundamental fitting; forward/backward traversal across image boundaries and empty-match pairs; integration through the publisher, output handler and human report; full EuRoC benchmark and GUI verification.
