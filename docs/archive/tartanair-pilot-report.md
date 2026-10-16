# LDO versus ORB comparison

Sequence: **ArchVizTinyHouseDay**

Controlled synthetic pilot; geometry-derived labels, no real-world or OOD claim.

XYZ remains external to both detectors. Unknown is not a false positive.

## TartanAir V2 reference-geometry pilot

Raw candidate metrics use K=5; these are retrieval proposals, not accepted loop closures. The exclusion is 5 seconds. Source trajectories last 9 to 15 seconds, so this pilot does not test long-term revisits.

Both detectors use identical grayscale cam0 frames. Reference depth/poses label outcomes only; operational verification uses observation stereo. IMU is installed but neither current detector consumes it.

| Method | Candidate pairs | Correct under overlap policy | False under overlap policy | Unknown | Precision bounds | Events detected / reference | Event recall | Accepted / pose-consistent |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- |
| orb | 453 | 53 | 347 | 53 | 0.1170 to 0.2340 | 10/10 | Unavailable | 40/39 |
| ldo | 453 | 61 | 324 | 68 | 0.1347 to 0.2848 | 10/10 | Unavailable | 142/117 |

Precision bounds assign every unknown return first as incorrect, then as correct. Overall event recall is unavailable when reference labels are incomplete; confirmed-event hits are a diagnostic subset.


### First candidate only (K=1)

| Method | Correct | False | Unknown | Precision bounds | Confirmed events detected |
| --- | ---: | ---: | ---: | --- | --- |
| orb | 19 | 77 | 10 | 0.1792 to 0.2736 | 8/10 |
| ldo | 32 | 65 | 9 | 0.3019 to 0.3868 | 10/10 |

### Reference-depth feature checks

| Method | Supported | Contradicted | Untestable | Judgeable fraction |
| --- | ---: | ---: | ---: | ---: |
| orb | 777 | 1609 | 1234 | 0.6591 |
| ldo | 7972 | 9007 | 18563 | 0.4777 |

Feature counts use each method's own returned candidates and reported assignments. They measure the complete approach, not an isolated matcher comparison; ORB retains its upstream extraction settings and LDO its pretrained configuration.


### Why reference depth cannot judge a feature match

Counts use the first failing gate across either endpoint; each unknown match appears once.

| Method | Outside / invalid pixel | Nonfinite depth | Depth outside range | Depth boundary |
| --- | ---: | ---: | ---: | ---: |
| orb | 0 | 0 | 413 | 821 |
| ldo | 0 | 0 | 6941 | 11622 |

### Accepted constraints: separate revisit and pose checks

| Method | Accepted | Overlap-positive | Overlap-negative | Overlap-unknown | Pose error exceeds tolerance |
| --- | ---: | ---: | ---: | ---: | ---: |
| orb | 40 | 28 | 3 | 9 | 1 |
| ldo | 142 | 57 | 38 | 47 | 25 |

A pose failure means the estimated relative transform exceeds 0.2 m or 5 degrees (provisional evaluation tolerances); it is not automatically a false revisit. An overlap-negative accepted constraint is false under the frozen 20% overlap policy, which is not proof that no physical surfaces are shared.


### Constraints meeting both independent checks

| Method | Pose-consistent and overlap-positive constraints | Confirmed event runs reached by these constraints |
| --- | ---: | --- |
| orb | 28 | 9/10 |
| ldo | 57 | 10/10 |

These are confirmed under the frozen overlap and provisional pose-error policies. Unknown pair labels remain unresolved, even if their pose estimate is accurate. Event hits cover the confirmed subset only.


### Per-trajectory candidate evaluation (K=5)

| Trajectory | Method | Correct | False | Unknown | Events detected / reference |
| --- | --- | ---: | ---: | ---: | --- |
| P000 | orb | 12 | 45 | 2 | 2/2 |
| P000 | ldo | 13 | 35 | 11 | 2/2 |
| P001 | orb | 6 | 43 | 10 | 1/1 |
| P001 | ldo | 6 | 42 | 11 | 1/1 |
| P002 | orb | 7 | 50 | 17 | 2/2 |
| P002 | ldo | 9 | 44 | 21 | 2/2 |
| P003 | orb | 6 | 86 | 2 | 1/1 |
| P003 | ldo | 7 | 85 | 2 | 1/1 |
| P004 | orb | 13 | 57 | 4 | 1/1 |
| P004 | ldo | 14 | 53 | 7 | 1/1 |
| P005 | orb | 4 | 37 | 18 | 2/2 |
| P005 | ldo | 7 | 36 | 16 | 2/2 |
| P006 | orb | 5 | 29 | 0 | 1/1 |
| P006 | ldo | 5 | 29 | 0 | 1/1 |

Labels measure a frozen minimum bidirectional visible-surface overlap, not manually established semantic place identity. Unknown reference coverage withholds overall recall. Continuous returns are not distinct events. This is a synthetic pilot in one environment, with unverified static-world assumptions and unaudited pretrained training overlap; it establishes neither OOD performance nor real-world superiority. Development-selected thresholds are not held-out results.

## Provenance and limitations

Configuration references, per-query and per-feature evidence, reference hashes and interval availability are retained in the companion JSON and benchmark artifact directory.

Candidate returns, accepted camera-derived constraints, reference overlap labels and pose errors are separate measurements. Full SLAM trajectory improvement and generalization are not established.
