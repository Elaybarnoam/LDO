# Experiment protocols and dataset-role history

Original protocols are preserved in the historical archive. This index identifies
their current use without rewriting the decisions recorded before each experiment.

| Study | Original protocol | Data roles and scope |
| --- | --- | --- |
| TartanAir pilot | [Reference geometry](../archive/tartanair-reference-geometry-plan.md) | Seven short TinyHouse trajectories; synthetic pilot with incomplete reference labels |
| Sequential optimization | [Sequential protocol](../archive/ldo-sequential-optimization-plan.md) | RetroOffice training, TinyHouse selection, CountryHouse frozen test |
| New-environment comparison | [Frozen test](../archive/ldo-unseen-tartanair-plan.md) | Factory/Desert were unused in this project's selection at execution; subsequently reused for matching development |
| Depth-v2 reference rescore | [Rescore protocol](../archive/reference-depth-v2-plan.md) | Saved Factory/Desert assignments; no detector rerun; pair/event policy retained |
| Matching optimization | [Matching protocol](../archive/ldo-matching-optimization-plan.md) | Factory/Desert fit/validation; frozen choice tested on OldTownFall, now inspected |
| Matching diagnosis | [Diagnostic protocol](../archive/ldo-matching-diagnostics-plan.md) | Saved evidence and reference-assisted capacities, not model improvements |
| Descriptor audit | [Descriptor protocol](../archive/ldo-descriptor-analysis-plan.md) | Positive development pairs; descriptor ranks and reference-assisted opportunity |
| EfficientLoFTR trial | [Joint-matching protocol](../archive/ldo-image-pair-matching-plan.md) | Same 880 development pairs; failed promotion, no fresh test/event replay |

## Requirements for the next experiment

Record the research question, baseline/variants, exact sequence and split IDs,
preprocessing, candidate population, temporal exclusion and budget, independent
reference policy/version, metrics/denominators, unknown treatment, promotion rules,
seeds, and stopping criteria before model selection. Pair/event retention rules
should preserve specific baseline identities, not only aggregate totals.

Identical-pair matcher ablations and end-to-end chronological detector replays
answer different questions. Retrieval-union pair sampling does not establish a
complete reference universe for overall recall. Pretraining dataset exposure and
shared synthetic assets remain unaudited.

Inspected test scenes become development evidence if used for a later choice.
OldTownFall's lost event may motivate a new question, but cannot be tuned against
and then reused as a fresh validation of that choice. New real-world, inertial,
and downstream SLAM claims require separate protocols and independent evidence.
