# LDO versus ORB: unseen TartanAir environments

Frozen confidence-only LDO: MegaLoc + SuperPoint + LightGlue, threshold 0.3. No candidate filter, adapted weights, training or tuning on these environments.

Both models receive identical grayscale cam0 frames, approximately 2 Hz, K=5 and a 5-second temporal exclusion. Each trajectory starts with an empty retrieval history. Neither detector consumes IMU or ground truth.

## Candidate image pairs and revisit events

Correct/false candidate labels use the frozen 20% minimum bidirectional visible surface-overlap rule. These are not accepted SLAM loops or pose-error counts. Event hits measure retrieval only: they do not require successful feature matching or an accepted pose.

| Environment | Detector | Correct pairs | False pairs | Unknown pairs | Confirmed event hits |
| --- | --- | ---: | ---: | ---: | --- |
| AbandonedFactory2 | orb | 651 | 1760 | 1188 | 23/29 |
| AbandonedFactory2 | ldo | 1351 | 830 | 1418 | 27/29 |
| DesertGasStation | orb | 224 | 984 | 1952 | 19/24 |
| DesertGasStation | ldo | 352 | 756 | 2052 | 21/24 |
| Combined | orb | 875 | 2744 | 3140 | 42/53 |
| Combined | ldo | 1703 | 1586 | 3470 | 48/53 |

### Candidate precision with unknown bounds

| Environment | Detector | Precision among known labels | Precision bounds including unknowns |
| --- | --- | ---: | --- |
| AbandonedFactory2 | orb | 27.0% | 18.1% to 51.1% |
| AbandonedFactory2 | ldo | 61.9% | 37.5% to 76.9% |
| DesertGasStation | orb | 18.5% | 7.1% to 68.9% |
| DesertGasStation | ldo | 31.8% | 11.1% to 76.1% |
| Combined | orb | 24.2% | 12.9% to 59.4% |
| Combined | ldo | 51.8% | 25.2% to 76.5% |

## Individual feature correspondences

Reference depth and camera poses independently judge every reported match. Correct means usable depths at both pixels, symmetric reprojection <=3 px, and XYZ distance <=max(0.05 m, 0.005 times maximum endpoint depth). Unknown depth evidence is never classified as incorrect.

| Environment | Detector | Correct matches | Incorrect matches | Unknown matches | Correct among judgeable | Judgeable coverage |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| AbandonedFactory2 | orb | 5974 | 17214 | 25985 | 25.8% | 47.2% |
| AbandonedFactory2 | ldo | 154417 | 224291 | 396982 | 40.8% | 48.8% |
| DesertGasStation | orb | 1715 | 5119 | 80672 | 25.1% | 7.8% |
| DesertGasStation | ldo | 19236 | 37946 | 259113 | 33.6% | 18.1% |
| Combined | orb | 7689 | 22333 | 106657 | 25.6% | 22.0% |
| Combined | ldo | 173653 | 262237 | 656095 | 39.8% | 39.9% |

### Correct-feature fraction bounds over all reported matches

| Environment | Detector | Bounds including unknowns |
| --- | --- | --- |
| AbandonedFactory2 | orb | 12.1% to 65.0% |
| AbandonedFactory2 | ldo | 19.9% to 71.1% |
| DesertGasStation | orb | 2.0% to 94.2% |
| DesertGasStation | ldo | 6.1% to 88.0% |
| Combined | orb | 5.6% to 83.7% |
| Combined | ldo | 15.9% to 76.0% |

## Per-trajectory candidate results

| Environment | Trajectory | Detector | Correct pairs | False pairs | Unknown pairs | Confirmed event hits |
| --- | --- | --- | ---: | ---: | ---: | --- |
| AbandonedFactory2 | P000 | orb | 157 | 439 | 273 | 5/6 |
| AbandonedFactory2 | P000 | ldo | 315 | 215 | 339 | 6/6 |
| AbandonedFactory2 | P001 | orb | 88 | 266 | 190 | 2/2 |
| AbandonedFactory2 | P001 | ldo | 182 | 81 | 281 | 2/2 |
| AbandonedFactory2 | P002 | orb | 111 | 357 | 66 | 3/4 |
| AbandonedFactory2 | P002 | ldo | 193 | 193 | 148 | 4/4 |
| AbandonedFactory2 | P003 | orb | 122 | 275 | 132 | 3/3 |
| AbandonedFactory2 | P003 | ldo | 220 | 203 | 106 | 3/3 |
| AbandonedFactory2 | P004 | orb | 44 | 208 | 227 | 5/9 |
| AbandonedFactory2 | P004 | ldo | 150 | 100 | 229 | 7/9 |
| AbandonedFactory2 | P005 | orb | 129 | 215 | 300 | 5/5 |
| AbandonedFactory2 | P005 | ldo | 291 | 38 | 315 | 5/5 |
| DesertGasStation | P000 | orb | 100 | 137 | 327 | 1/1 |
| DesertGasStation | P000 | ldo | 127 | 143 | 294 | 1/1 |
| DesertGasStation | P001 | orb | 23 | 174 | 312 | 3/3 |
| DesertGasStation | P001 | ldo | 37 | 133 | 339 | 3/3 |
| DesertGasStation | P002 | orb | 43 | 274 | 432 | 6/8 |
| DesertGasStation | P002 | ldo | 91 | 170 | 488 | 7/8 |
| DesertGasStation | P003 | orb | 50 | 110 | 494 | 5/6 |
| DesertGasStation | P003 | ldo | 69 | 143 | 442 | 5/6 |
| DesertGasStation | P004 | orb | 8 | 289 | 387 | 4/6 |
| DesertGasStation | P004 | ldo | 28 | 167 | 489 | 5/6 |

## Per-trajectory feature results

| Environment | Trajectory | Detector | Correct matches | Incorrect matches | Unknown matches | Correct among judgeable |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| AbandonedFactory2 | P000 | orb | 1272 | 4576 | 10831 | 21.8% |
| AbandonedFactory2 | P000 | ldo | 28280 | 73721 | 130261 | 27.7% |
| AbandonedFactory2 | P001 | orb | 948 | 2163 | 2058 | 30.5% |
| AbandonedFactory2 | P001 | ldo | 23836 | 29888 | 46459 | 44.4% |
| AbandonedFactory2 | P002 | orb | 1719 | 3865 | 1591 | 30.8% |
| AbandonedFactory2 | P002 | ldo | 35346 | 28103 | 35808 | 55.7% |
| AbandonedFactory2 | P003 | orb | 1172 | 4019 | 5697 | 22.6% |
| AbandonedFactory2 | P003 | ldo | 23182 | 31953 | 45216 | 42.0% |
| AbandonedFactory2 | P004 | orb | 296 | 1060 | 2005 | 21.8% |
| AbandonedFactory2 | P004 | ldo | 15145 | 24446 | 48970 | 38.3% |
| AbandonedFactory2 | P005 | orb | 567 | 1531 | 3803 | 27.0% |
| AbandonedFactory2 | P005 | ldo | 28628 | 36180 | 90268 | 44.2% |
| DesertGasStation | P000 | orb | 1044 | 1448 | 4368 | 41.9% |
| DesertGasStation | P000 | ldo | 6614 | 7987 | 31252 | 45.3% |
| DesertGasStation | P001 | orb | 227 | 823 | 2280 | 21.6% |
| DesertGasStation | P001 | ldo | 3029 | 11302 | 35707 | 21.1% |
| DesertGasStation | P002 | orb | 63 | 1061 | 65074 | 5.6% |
| DesertGasStation | P002 | ldo | 1134 | 2391 | 120710 | 32.2% |
| DesertGasStation | P003 | orb | 296 | 1067 | 1748 | 21.7% |
| DesertGasStation | P003 | ldo | 5189 | 7102 | 17873 | 42.2% |
| DesertGasStation | P004 | orb | 85 | 720 | 7202 | 10.6% |
| DesertGasStation | P004 | ldo | 3270 | 9164 | 53571 | 26.3% |

## Interpretation limits

- These environments were unused in our own development; upstream pretrained exposure and shared synthetic assets are unaudited.
- Unknown reference evidence can differ between methods. Judgeable precision is not accuracy across all reported matches; compare the bounds and coverage.
- A smaller absolute count of wrong feature matches is not a fair error-rate comparison when output densities differ.
- Confirmed-event hits do not establish overall recall when reference labels are incomplete. Redundant pairs do not count as additional events.
- The unchanged 50 m depth limit and depth-boundary gates can reduce outdoor reference coverage. They were not retuned on these test scenes.
- The original EuRoC XYZ evaluator is unchanged. This experiment uses simulator reference depth directly; no stereo estimator, RANSAC, PnP or operational verifier is involved.
- No latency, real-world superiority, or downstream SLAM trajectory improvement is established here.

## Provenance

Freeze SHA256: `8d32fe9955b735c41f5f53cbaaf5d0a9f859c48914d00a60e08e6d3f257129fb`

- AbandonedFactory2: `/opt/loop-detector/experiments/tartanair_unseen/AbandonedFactory2/comparison_2026-10-10_15-30-09_831234_28883164.json` (SHA256 `1d3eaf3fb7579d55b6d0c8dd9ef608cdf1d7266c16d9c4f30d124598039ab645`).
- DesertGasStation: `/opt/loop-detector/experiments/tartanair_unseen/DesertGasStation/comparison_2026-10-10_15-33-46_407681_5b07f062.json` (SHA256 `404570e00909d3132af7e5085e0e8395dcdf2813a78762fdcc7ce9f152b011a4`).
