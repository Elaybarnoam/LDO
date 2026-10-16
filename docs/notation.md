# Notation and interface conventions

| Symbol / field | Meaning | Convention |
| --- | --- | --- |
| $q,h$ | Query and historical frame identifiers | Identifiers are not timestamps |
| $I_q,I_h$ | Original camera images | Current detector uses cam0; explicit session identity |
| $t_q,t_h$ | Timestamps | Strictly increasing integer nanoseconds in contracts |
| $\Delta$ | Temporal exclusion | Convert seconds to integer nanoseconds explicitly |
| $k$ | Retrieval budget | Positive integer; eligibility precedes ranking |
| $K_q,K_h$ | Intrinsics | Pixels; distinct from candidate budget $k$ |
| $u,v$ | Query/history pixels | $(x,y)$ in original image coordinates |
| $\tilde u$ | Homogeneous pixel | $(x,y,1)^\top$ |
| $z$ | Axial camera depth | Metres along optical Z, not ray range |
| $X_A$ | A point expressed in frame A | Metres; column-vector convention in equations |
| $T_{AB}$ | Transform from B to A | $X_A=R_{AB}X_B+t_{AB}$ |
| $T_{Wq},T_{Wh}$ | Camera-to-world reference poses | Offline reference evidence only |
| $d_q$ | Global descriptor | Normalized finite float32 representation with fingerprint |
| $\mathcal C_q$ | Ordered candidates | Historical identifiers with retrieval scores |
| $\mathcal M_{qh}$ | Reported assignments | Sparse feature IDs or explicitly pair-dependent pixels |
| $c_{ij}$ | Matcher score | Adapter-defined confidence, not a calibrated probability |
| $y_{qh}$ | Independent pair label | loop / non-loop / unknown |
| $a_{qh}$ | Operational outcome | accepted / rejected / insufficient_evidence |
| $S,C,U$ | Feature verdict counts | supported / contradicted / unknown (`untestable` in evidence) |

## Geometry details

The runtime verifier returns `T_HQ`: query-camera coordinates map into the
historical camera. NumPy routines may use row-vector storage, implementing the
same action as `points @ R.T + t`. Matrix composition in equations uses column
vectors. Translations are metric; pose rotation errors are reported in degrees.

Runtime raw-camera projection includes supplied distortion coefficients. Simple
$K^{-1}\tilde u$ backprojection assumes undistorted pinhole pixels; it must not be
applied to distorted observations without the matching calibration operation.

TartanAir reference checks use the documented camera-frame conversion and
array-index pixel centers. The installed 640×640 pinhole reference has focal
length 320 pixels and principal point (319.5, 319.5). Packed depth is decoded
losslessly as little-endian float32. Those are dataset-adapter conventions, not
universal properties of camera observations.

Resizing extraction does not change the coordinate frame of exported keypoints.
Matching output and evidence always refer back to original camera pixels.

## Interface semantics

- Frames are processed once in strictly increasing time within a session; reset
  before switching sessions. Query before inserting the current frame.
- Local feature arrays are finite and read-only; feature dimensions, image bounds,
  descriptor family, and representation fingerprints are validated.
- Sparse assignments have unique endpoint IDs on each side. Pair-dependent
  pixel observations do not imply stable cached sparse feature identities.
- An inference failure makes the detector unusable until a fresh instance is
  initialized; partial state is not silently continued.
- Similarity and matcher scores retain their adapter-specific meaning. Neither
  score is automatically a place-correctness probability.

See [method](method.md) for equations and [architecture](architecture.md) for source links.
