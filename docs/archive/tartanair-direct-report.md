# LDO versus ORB comparison

Sequence: **ArchVizTinyHouseDay**

Direct reference-depth correspondence evaluation; short synthetic pilot, no overall superiority claim.

XYZ remains external to both detectors. Unknown is not a false positive.

## Direct reference-depth evaluation

Every reported feature assignment is checked using TartanAir reference depth and camera poses. No learned stereo estimation, PnP, RANSAC, operational verifier or pose acceptance filter is used. The detector outputs are unchanged; ground truth is evaluator-only.

| Method | Candidate pairs | Reported feature matches | Supported | Contradicted | Unknown | Judgeable coverage | Correct among judgeable |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| orb | 453 | 3620 | 777 | 1609 | 1234 | 65.9% | 32.6% |
| ldo | 453 | 35542 | 7972 | 9007 | 18563 | 47.8% | 47.0% |

Reference support requires XYZ distance <= max(0.05 m, 0.005 times maximum endpoint depth) and symmetric reprojection error <= 3 pixels, with usable reference depth at both endpoints.


Contradicted means the reported feature locations disagree under the frozen XYZ/reprojection tolerances. Unknown features are not false positives. These are feature-correspondence judgments, not counts of false loop closures. A different number of assignments and unknown coverage prevents a conclusion from absolute counts alone.

### Bounds including unknown feature matches

| Method | Supported fraction bounds | Contradicted fraction bounds | Zero-match candidate pairs |
| --- | --- | --- | ---: |
| orb | 21.5% to 55.6% | 44.4% to 78.5% | 13 |
| ldo | 22.4% to 74.7% | 25.3% to 77.6% | 8 |

### Independent image-pair retrieval (K=5)

| Method | Overlap-positive | Overlap-negative | Unknown | Confirmed event runs reached |
| --- | ---: | ---: | ---: | --- |
| orb | 53 | 347 | 53 | 10/10 |
| ldo | 61 | 324 | 68 | 10/10 |

Image-pair labels use the frozen 20% bidirectional surface-overlap policy, independently of reported feature matches. Event hits cover confirmed runs only; overall recall is withheld when the reference universe is incomplete.

### Unknown reference depth: first failing gate

| Method | Outside/invalid pixel | Nonfinite depth | Depth outside range | Depth boundary |
| --- | ---: | ---: | ---: | ---: |
| orb | 0 | 0 | 413 | 821 |
| ldo | 0 | 0 | 6941 | 11622 |

### Per-trajectory feature judgments

| Trajectory | Method | Supported | Contradicted | Unknown |
| --- | --- | ---: | ---: | ---: |
| P000 | orb | 229 | 312 | 313 |
| P000 | ldo | 1835 | 1639 | 4342 |
| P001 | orb | 67 | 182 | 93 |
| P001 | ldo | 605 | 922 | 653 |
| P002 | orb | 73 | 224 | 276 |
| P002 | ldo | 1160 | 1439 | 4184 |
| P003 | orb | 132 | 317 | 129 |
| P003 | ldo | 876 | 1385 | 1903 |
| P004 | orb | 129 | 252 | 143 |
| P004 | ldo | 1627 | 1481 | 3785 |
| P005 | orb | 110 | 177 | 220 |
| P005 | ldo | 1107 | 1379 | 2863 |
| P006 | orb | 37 | 145 | 60 |
| P006 | ldo | 762 | 762 | 833 |

Depth sampling, uncertainty masks and numerical tolerances remain frozen. This is a short synthetic pilot in one environment, using each detector's own returned candidates. Static-world and pretrained training-overlap assumptions are unaudited. It establishes neither real-world superiority nor OOD performance. Historical operational pose-failure counts are not measurements in this experiment.

## Provenance and limitations

The companion JSON and artifact directory retain original detector evidence hashes, reference hashes, per-feature world coordinates and numerical errors. No operational acceptance or fitted pose is measured in this experiment.

This short synthetic pilot does not establish full SLAM trajectory improvement or generalization.
