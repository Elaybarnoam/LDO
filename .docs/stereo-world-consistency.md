# Stereo landmark XYZ consistency

Status: implemented in `evaluation/src/tasks/feature_matching/xyz/stereo.py`;
enabled by version 4 of the independent checker configuration.

## Calculation

For a candidate between query q and historical h, use four raw images:
cam0/cam1 at q and cam0/cam1 at h. Temporal ORB matches associate cam0 features
between q and h. Separate mutual stereo ORB matches provide depth at each time.

Each camera uses its own dataset intrinsics/distortion and body extrinsics:

`T_C1C0 = inverse(T_BC1) * T_BC0`

Undistort pixels into normalized rays and triangulate with `[I|0]` and
`[R_C1C0|t_C1C0]`. The resulting XYZ is in original cam0 axes; no rectification
rotation is mixed with camera/body calibration.

`P_Wq = T_WBq * T_BC0 * P_Cq`

`P_Wh = T_WBh * T_BC0 * P_Ch`

`delta = P_Wq - P_Wh`

Reference sensor-to-body calibration is also applied when constructing T_WB.
Report Euclidean discrepancy `norm(delta)` and squared Mahalanobis discrepancy
`delta.T * inverse(C_Wq + C_Wh) * delta`. Project P_Wh into query cam0 and P_Wq
into historical cam0, requiring small pixel errors in both directions.

## Reliability and outcomes

Reject invalid stereo depth before counting a landmark: positive depth in both
cameras, acceptable reprojection, sufficient parallax, permitted depth range,
and bounded relative depth uncertainty. Require reliable depth at **both**
timestamps. Missing synchronized cam1 or reference pose stays inconclusive.

Let N be the number of reported temporal ORB feature correspondences, before
stereo filtering. Version 4 requires ceil(0.4 × N) passing landmarks for support,
plus distributed image coverage. There is no fixed 20-landmark support gate.
Depth availability is depth-valid/N; support is passing/N. If fewer than the
required number have usable depth, the outcome is insufficient evidence.
Suspicion requires at least that same number of usable depths, distributed
paired coverage, and at most 10% agreement among depth-valid landmarks.
Missing depth never counts as geometric disagreement.

## Uncertainty assumptions

The implementation estimates triangulation covariance using a numerical
Jacobian with respect to four raw image coordinates and assumed 1 px noise.
World covariance adds assumed 0.03 m position noise and 1Â° orientation noise
per reference pose. This is a first-order model; calibration uncertainty and
cross-pose correlations are not modeled. Dataset reference covariance is not
available in this interface.

The reported three-sigma radius is along the largest covariance axis, not an
isotropic XYZ acceptance threshold. Mahalanobis error accounts for covariance
direction. Cross-view reprojection currently uses a fixed provisional 7 px
gate; it is not a calibrated uncertainty probability.

These estimates are **reconstructed feature XYZ**, anchored using reference
trajectory poses. They are not ground-truth feature XYZ and do not establish
definitive TP/FP labels.

## Retained evidence

Each native run's `candidate_checks/pairs.jsonl` retains original image
coordinates, local/world XYZ for both observations, metric and covariance
weighted disagreement, assumed uncertainty radius, bidirectional reprojection,
and the landmark consistency decision. Right-camera image identities and hashes
are retained for each pair.

The publisher sends compact measurements and evidence-file/line references to
the existing singleton writer. The Markdown report summarizes outcomes,
landmark totals, noise assumptions and examples. No reference information is
fed back into detector retrieval.

## Verification

Tests reconstruct known 3D points using different distorted camera models and
nonidentity stereo rotations; check world-coordinate agreement under camera
motion; verify both cross projections; reject reversed disparity and low
parallax; and exercise supported, contradictory and missing-right-image cases
through the real evaluator. The evaluation suite contains 37 passing tests.

MH_01_easy run `evaluation_2026-10-02_17-51-31_822309_c3901e7f` completed all
1,635 candidate checks: 224 supported, 206 suspicious, 1,205 inconclusive.
It produced 36,935 landmark comparison records, including 14,617 that passed
the joint XYZ/reprojection gates. These records are repeated observations, not
unique scene landmarks.
