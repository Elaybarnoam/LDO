# Dataset and model assets

Bulk data, model weights, and generated evidence are not tracked. Use the pinned
installers and the study's original protocol; preserve archive/checkpoint hashes,
calibration, input order, and timestamp conventions. The historical dataset roots
remain under `evaluation/datasets/` or external WSL storage during this migration.

TartanAir studies use dataset revision
`0d2d145e973832742a2aaa04b7d2ebffc8d82817` from `theairlabcmu/tartanair2`.
The installer checks archive hashes. Reference depth and poses are offline evidence
and are excluded from detector/operational-verifier inputs.

See [dataset manifests](manifests/datasets.json), [installation](../docs/installation.md),
and [protocol history](../docs/protocols/README.md). Dataset downloads and pretrained
weights have their own terms. Repository visibility does not grant permission to
redistribute upstream assets. Published diagnostic images retain their original
provenance; redistribution permission should be confirmed before a public release.
