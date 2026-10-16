# Licensing and third-party terms

Copyright 2026 Elay Barnoam. Original LDO code and documentation are available
under [Apache License 2.0](../LICENSE), subject to the exceptions in [NOTICE](../NOTICE).
This license permits reuse of the original project code; it does not grant rights
to third-party source, models, weights, datasets or trademarks.

## Scope and exceptions

| Component | Scope and source |
| --- | --- |
| Original LDO Python, configs, documentation and presentation generators | Apache-2.0 |
| ORB-SLAM3 instrumentation | `src/loop_eval/benchmarks/orb_slam3/instrumentation/` is GPL-3.0-or-later, matching its integration with [ORB-SLAM3](https://github.com/UZ-SLAMLab/ORB_SLAM3/blob/master/LICENSE); the directory carries its own license |
| MegaLoc | External source at the revision in [upstream.lock.json](../src/ldo/upstream.lock.json); [MIT](https://github.com/gmberton/MegaLoc/blob/5fe0dd697c4a70ba3e23607f6716ab3c606b16db/LICENSE) source terms do not by themselves establish rights to every training dataset or checkpoint |
| LightGlue | External source; [Apache-2.0 with component notices](https://github.com/cvg/LightGlue/blob/eb42fee2d71449efb0aa5c10549752b5d75384d8/LICENSE) |
| SuperPoint | Separate Magic Leap notices in [the pinned implementation](https://github.com/cvg/LightGlue/blob/eb42fee2d71449efb0aa5c10549752b5d75384d8/lightglue/superpoint.py); the project's Apache license does not override these restrictions |
| EfficientLoFTR | External candidate used in a failed promotion trial; consult the [license at the experiment's pinned revision](https://github.com/zju3dv/EfficientLoFTR/blob/07e9c1401e71e9c556b1fda9d86d060af36ba176/LICENSE) and its checkpoint terms |
| Stereo and other native/model runtimes | Installed separately; retain source/weight notices from their installation manifests |
| TartanAir / EuRoC and image derivatives | Dataset-specific terms, separate from LDO; acquisition sources and roles are in [data](../data/README.md) and [dataset metadata](../data/manifests/datasets.json) |

The archived matching figures and community walkthrough contain TartanAir
OldTownFall simulated scene imagery. Preserve attribution and the upstream dataset
terms when redistributing these images. The community manifest records which
archived images were used. No raw dataset or checkpoint is bundled in the release.

Image attribution: TartanAir / AirLab, Carnegie Mellon University; see
[TartanAir documentation](https://tartanair.org/), which identifies the v2 dataset
as [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The
[Hugging Face dataset card](https://huggingface.co/datasets/theairlabcmu/tartanair2)
also carries BSD-3-Clause metadata; preserve the terms supplied with your acquired
assets rather than assuming the toolkit and dataset share a license. The community
presentation resizes archived annotated figures and adds explanatory captions;
it does not change scene pixels, match positions or evaluator verdicts.

The default learned stack includes SuperPoint. Do not infer that every optional
pipeline is available for unrestricted commercial use from the root license.
Review the terms for the exact sources, weights and datasets you choose.

## Contributions

Contribute original work you are entitled to submit. Unless explicitly agreed
otherwise, contributions to Apache-licensed files use Apache-2.0; contributions to
the GPL instrumentation use that directory's license. Preserve existing notices
and document any new third-party material. Historical evidence remains immutable;
licensing documentation does not alter its provenance or original bytes.
