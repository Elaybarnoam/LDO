# Figures and provenance

| Figure | Kind and selection | Evidence |
| --- | --- | --- |
| `diagrams/system-overview` | Implemented architecture schematic | Runtime/reference module interfaces; not a measurement |
| `diagrams/coordinate-conventions` | Query-to-history frame schematic | Tested transform convention; not a calibrated scene |
| `figures/matching-tradeoff` | All OldTownFall test trajectories | Matching optimization saved aggregate; depth-v2 feature policy |
| `figures/joint-matcher-trial` | All 320 identical validation pairs | Failed EfficientLoFTR trial; supported/contradicted/unknown counts |
| `figures/retrieval-evidence` | All 11 original Factory/Desert trajectories | Original independent pair labels and confirmed-event counts |
| Historical matching-diagnostic PNGs | Four saved failure events | Original figure/image/evidence hashes in the archived figure manifest |
| `community/evidence-walkthrough` | 24-second presentation of two archived failure pairs | Selected TartanAir simulation evidence; no inference or operational decision |
| `community/social-preview` | Repository share card with an intact archived figure | Presentation asset; separate upstream image terms |

Regenerate:

```bash
uv sync --locked --extra visualization
uv run python scripts/reproduce/publish.py --figures docs/assets/figures
uv run python scripts/figures/render_diagrams.py
uv run python scripts/figures/render_community.py --output artifacts/community
```

Quantitative graphics have SVG/PDF exports and PNG previews. Diagram sources are
the editable rendering script. Each asset directory contains a manifest recording
generator and output hashes; quantitative figures name their experiment and
selection rule. Result manifests record source-summary hashes. `scripts/check_repository.py`
checks these chains. Rendering software/platform changes can alter image bytes;
compare numerical tables before interpreting rendering differences.

Historical PNGs are preserved, not redrawn or relabeled as new model results.
See the [original figure provenance](../archive/ldo-matching-diagnostics-figures.json).
Unknown is distinct from contradicted. Use readable labels/captions and alternative
text; scientific evidence must not be replaced by generated illustrative imagery.
