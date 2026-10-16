# LDO feature matching optimization

Identical fixed image pairs, pretrained weights and unchanged independent depth-v2 evaluation. Previously inspected factory/desert scenes are development data; no new unseen claim is made for them.

## Sequential decisions

| Step | Fit-selected configuration | Promoted on validation | Kept configuration |
| --- | --- | --- | --- |
| confidence | 8922914faaee505d | True | 8922914faaee505d |
| full_depth | 8922914faaee505d | False | 8922914faaee505d |
| keypoint_count | 8922914faaee505d | False | 8922914faaee505d |
| image_resolution | 8922914faaee505d | False | 8922914faaee505d |
| feature_family | 8922914faaee505d | False | 8922914faaee505d |

## All development variants

| Configuration | Split | Correct | Incorrect | Unknown | Precision among judged | Coverage | Usable genuine pairs |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 67f8fc63645fb533 | fit | 28748 | 44145 | 16600 | 39.4% | 81.5% | 181/224 |
| 67f8fc63645fb533 | validate | 13360 | 20845 | 6801 | 39.1% | 83.4% | 104/128 |
| 8922914faaee505d | fit | 27915 | 38995 | 15692 | 41.7% | 81.0% | 179/224 |
| 8922914faaee505d | validate | 12934 | 17806 | 6282 | 42.1% | 83.0% | 102/128 |
| 50fe5619e30770c9 | fit | 27008 | 34613 | 14872 | 43.8% | 80.6% | 179/224 |
| 50fe5619e30770c9 | validate | 12452 | 15279 | 5782 | 44.9% | 82.7% | 102/128 |
| 2439880df5a0cf6d | fit | 25996 | 30471 | 14021 | 46.0% | 80.1% | 177/224 |
| 2439880df5a0cf6d | validate | 11888 | 13110 | 5260 | 47.6% | 82.6% | 101/128 |
| 42292a3c60d955de | fit | 28539 | 40048 | 15696 | 41.6% | 81.4% | 179/224 |
| 42292a3c60d955de | validate | 13296 | 18461 | 6321 | 41.9% | 83.4% | 103/128 |
| 82ca78f39a3ab468 | fit | 15571 | 21955 | 8904 | 41.5% | 80.8% | 164/224 |
| 82ca78f39a3ab468 | validate | 7122 | 9602 | 3283 | 42.6% | 83.6% | 98/128 |
| 69be9c628529265f | fit | 42573 | 59331 | 21600 | 41.8% | 82.5% | 179/224 |
| 69be9c628529265f | validate | 19101 | 26049 | 9104 | 42.3% | 83.2% | 107/128 |
| c284ac4363adaf8c | fit | 16050 | 25899 | 22924 | 38.3% | 64.7% | 159/224 |
| c284ac4363adaf8c | validate | 6481 | 10960 | 10662 | 37.2% | 62.1% | 85/128 |
| a07fad66fa56af37 | fit | 24065 | 22818 | 34593 | 51.3% | 57.5% | 179/224 |
| a07fad66fa56af37 | validate | 10390 | 9907 | 15740 | 51.2% | 56.3% | 102/128 |
| ec7eca6904ae04e1 | fit | 31012 | 23565 | 31738 | 56.8% | 63.2% | 175/224 |
| ec7eca6904ae04e1 | validate | 12266 | 9802 | 14199 | 55.6% | 60.8% | 99/128 |
| ORB same pairs | fit | 1642 | 3333 | 6434 | 33.0% | 43.6% | 15/224 |
| ORB same pairs | validate | 531 | 967 | 1484 | 35.4% | 50.2% | 5/128 |

## Configuration identities

- `67f8fc63645fb533`: `{'family': 'superpoint', 'keypoints': 1024, 'resize': None, 'full_depth': False, 'threshold': 0.3}`
- `8922914faaee505d`: `{'family': 'superpoint', 'keypoints': 1024, 'resize': None, 'full_depth': False, 'threshold': 0.4}`
- `50fe5619e30770c9`: `{'family': 'superpoint', 'keypoints': 1024, 'resize': None, 'full_depth': False, 'threshold': 0.5}`
- `2439880df5a0cf6d`: `{'family': 'superpoint', 'keypoints': 1024, 'resize': None, 'full_depth': False, 'threshold': 0.6}`
- `42292a3c60d955de`: `{'family': 'superpoint', 'keypoints': 1024, 'resize': None, 'full_depth': True, 'threshold': 0.4}`
- `82ca78f39a3ab468`: `{'family': 'superpoint', 'keypoints': 512, 'resize': None, 'full_depth': False, 'threshold': 0.4}`
- `69be9c628529265f`: `{'family': 'superpoint', 'keypoints': 2048, 'resize': None, 'full_depth': False, 'threshold': 0.4}`
- `c284ac4363adaf8c`: `{'family': 'superpoint', 'keypoints': 1024, 'resize': 480, 'full_depth': False, 'threshold': 0.4}`
- `a07fad66fa56af37`: `{'family': 'superpoint', 'keypoints': 1024, 'resize': 960, 'full_depth': False, 'threshold': 0.4}`
- `ec7eca6904ae04e1`: `{'family': 'aliked', 'keypoints': 1024, 'resize': None, 'full_depth': False, 'threshold': 0.4}`

Selected: `{'family': 'superpoint', 'keypoints': 1024, 'resize': None, 'full_depth': False, 'threshold': 0.4}`

## Fresh OldTownFall end-to-end test

| Detector | Correct | Incorrect | Unknown | Precision among judged | Coverage | Raw event hits | Events with usable correspondences |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| orb | 791 | 5689 | 2298 | 12.2% | 73.8% | 11/17 | 2/17 |
| baseline | 40003 | 100983 | 9879 | 28.4% | 93.5% | 17/17 | 13/17 |
| selected | 38673 | 83526 | 8457 | 31.6% | 93.5% | 17/17 | 12/17 |

### Raw candidate retrieval

| Detector | Correct pairs | False pairs | Unknown pairs |
| --- | ---: | ---: | ---: |
| orb | 139 | 966 | 1002 |
| baseline | 262 | 477 | 1368 |
| selected | 262 | 477 | 1368 |

## Limits and provenance

- Usable means >=20 independently correct correspondences on a reference-positive pair. This is an evaluator diagnostic, not a runtime ground-truth filter or an accepted SLAM loop.
- Promotions require cumulative baseline retention per scene and overall: >=90% correct matches, >=95% usable genuine pairs, nondecreasing judged precision, and fewer bad matches on fit and validation.
- Threshold filtering and feature changes can discard correct matches; all failed promotions are retained in the report. Unknowns are never counted as incorrect.
- Pair labels retain the original overlap policy; depth-v2 judges features separately. Incomplete reference labels withhold overall recall claims.
- Shared scenes across development splits and one new synthetic test environment do not establish real-world or universal superiority. Upstream pretraining exposure is unaudited.
- No fine-tuning, RANSAC selection, downstream SLAM trajectory test or latency promotion is performed.

Artifact root: `/opt/loop-detector/experiments/matching_optimization`

Pair-list SHA256: `3ec31808f210f2b5564b92e0c296e46cf3d06fe1be818c4cb9041d9ac1f2b93a`

Experiment freeze SHA256: `2f4401a8256f9d6fe6fbd409a985360f935516a37a6367e1fcbc8cb1c916e0db`

Selected configuration SHA256: `2596c24c3806e9580a6bfa01b29b296a5307fcd5361df8ab71fbf4ccfdc0e1e7`
