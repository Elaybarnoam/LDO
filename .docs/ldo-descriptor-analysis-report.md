# LDO descriptor and assignment analysis

Frozen SuperPoint/LightGlue confidence-0.3 baseline. Development data only; TartanAir provides ground-truth depth and poses. No inference, training or promotion occurred.

## Rank-restricted geometric capacity

A usable pair has at least 20 reference-supported one-to-one correspondences. This is a diagnostic, not SLAM acceptance. Top-k restricts the SAME supported edge's raw descriptor cosine ranks; reciprocal requires both directions.

| Split / scene | Pairs | Baseline usable | Geometry capacity ≥20 | Reciprocal top-1 ≥20 | Reciprocal top-5 ≥20 | Reciprocal top-10 ≥20 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| fit / Overall | 224 | 181 | 224 | 179 | 203 | 206 |
| fit / AbandonedFactory2 | 128 | 117 | 128 | 122 | 128 | 128 |
| fit / DesertGasStation | 96 | 64 | 96 | 57 | 75 | 78 |
| validate / Overall | 128 | 104 | 128 | 93 | 112 | 117 |
| validate / AbandonedFactory2 | 64 | 61 | 64 | 60 | 63 | 63 |
| validate / DesertGasStation | 64 | 43 | 64 | 33 | 49 | 54 |

## Pairs the baseline could not make usable

| Split | Gap pairs | Forward top-1 capacity ≥20 | Reciprocal top-1 ≥20 | Reciprocal top-5 ≥20 | Reciprocal top-10 ≥20 | Reciprocal top-50 ≥20 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| fit | 43 | 15 | 6 | 23 | 25 | 34 |
| validate | 24 | 3 | 1 | 9 | 13 | 21 |

## Missing associations

### fit

- 8,615 query features have a geometrically supported alternative but no supported baseline assignment; 7,119 are unassigned.
- Among those missing supported queries: 22.8% have a forward top-1 alternative, 50.7% have a forward top-5 alternative, 61.5% have a forward top-10 alternative.
- 435/24,616 contradicted assignments have a higher-cosine supported alternative for the same query feature.

### validate

- 4,642 query features have a geometrically supported alternative but no supported baseline assignment; 4,234 are unassigned.
- Among those missing supported queries: 18.8% have a forward top-1 alternative, 40.8% have a forward top-5 alternative, 50.3% have a forward top-10 alternative.
- 126/11,312 contradicted assignments have a higher-cosine supported alternative for the same query feature.

## Interpretation limits

- Compatible geometry does not prove unique visual identity or visibility.
- Raw SuperPoint similarity is not LightGlue's contextual assignment score. High raw ranks expose opportunities, not proof of a specific internal model bug.
- Every keypoint competes in ranking, including those with unknown reference evidence.
- Ties within 1e-7 receive the conservative worst tied rank.
- These are selected positive development pairs; do not infer global false-loop precision.
- No model accuracy improvement, event recovery or native SLAM acceptance is claimed.
- New model choices require complete development replays, event-preserving promotion checks and a frozen fresh-environment test.

## Provenance

- Freeze SHA256: `4811d3cecef75738ec5a18ef18f9a4c2225674dc6584c9ee208927843e206740`
- Artifact root: `/opt/loop-detector/experiments/descriptor_analysis/v1`
- Per-pair NPZ records supported-edge ranks, actual-assignment ranks and cosine scores.
- Inputs, descriptors, geometry edges and original assignments were hash checked.
