# LDO feature matching optimization

Identical fixed image pairs, pretrained weights and unchanged independent depth-v2 evaluation. Previously inspected factory/desert scenes are development data; no new unseen claim is made for them.

## Sequential decisions

| Step | Fit-selected configuration | Promoted on validation | Kept configuration |
| --- | --- | --- | --- |
| EfficientLoFTR preliminary pair gate; production promotion pending | 67f8fc63645fb533 | False | 67f8fc63645fb533 |

## All development variants

| Configuration | Split | Correct | Incorrect | Unknown | Precision among judged | Coverage | Usable genuine pairs |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 67f8fc63645fb533 | fit | 28748 | 44145 | 16600 | 39.4% | 81.5% | 181/224 |
| 67f8fc63645fb533 | validate | 13360 | 20845 | 6801 | 39.1% | 83.4% | 104/128 |
| efficientloftr-native-full-0.2-1024 | fit | 123581 | 160361 | 79768 | 43.5% | 78.1% | 197/224 |
| efficientloftr-native-full-0.2-1024 | validate | 61216 | 77742 | 45861 | 44.1% | 75.2% | 117/128 |
| ORB same pairs | fit | 1642 | 3333 | 6434 | 33.0% | 43.6% | 15/224 |
| ORB same pairs | validate | 531 | 967 | 1484 | 35.4% | 50.2% | 5/128 |

## Configuration identities

- `67f8fc63645fb533`: `{'family': 'superpoint', 'keypoints': 1024, 'resize': None, 'full_depth': False, 'threshold': 0.3}`
- `efficientloftr-native-full-0.2-1024`: `{'engine': 'efficientloftr', 'precision': 'fp32', 'resize': None, 'threshold': 0.2, 'maximum_matches': 1024}`

Selected: `{'family': 'superpoint', 'keypoints': 1024, 'resize': None, 'full_depth': False, 'threshold': 0.3}`

## Fresh test

Not run yet. No test-data promotion decisions are permitted.

## Limits and provenance

- Usable means >=20 independently correct correspondences on a reference-positive pair. This is an evaluator diagnostic, not a runtime ground-truth filter or an accepted SLAM loop.
- Promotions require cumulative baseline retention per scene and overall: >=90% correct matches, >=95% usable genuine pairs, nondecreasing judged precision, and fewer bad matches on fit and validation.
- Threshold filtering and feature changes can discard correct matches; all failed promotions are retained in the report. Unknowns are never counted as incorrect.
- Pair labels retain the original overlap policy; depth-v2 judges features separately. Incomplete reference labels withhold overall recall claims.
- Shared scenes across development splits and one new synthetic test environment do not establish real-world or universal superiority. Upstream pretraining exposure is unaudited.
- No fine-tuning, RANSAC selection, downstream SLAM trajectory test or latency promotion is performed.

Artifact root: `/opt/loop-detector/experiments/image_pair_matching/v1`

Pair-list SHA256: `3ec31808f210f2b5564b92e0c296e46cf3d06fe1be818c4cb9041d9ac1f2b93a`

Experiment freeze SHA256: `46964d6dc399a51abeb5a42acf23e69d7a4f5669e332ececf6ce00b247bcff5b`

Selected configuration SHA256: `f303e13e43f0c0bba20a5ee35d15c36aeec68d052bdb6067053e630b448b1851`
