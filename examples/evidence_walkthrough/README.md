# Saved-evidence walkthrough

This 24-second animation presents two diagnosed OldTownFall revisit pairs from
the existing TartanAir study. It shows saved learned-model correspondences and
separate reference-only capacity diagnostics. It does not rerun inference, animate
a trajectory, show a runtime rejection, or demonstrate real-world performance.
The two events were selected for different failure mechanisms, not as a random
sample or a performance estimate.

```bash
uv sync --locked --extra visualization
uv run python scripts/figures/render_community.py --output artifacts/community
```

Open `artifacts/community/evidence-walkthrough.gif`. The same command also writes
a static poster, a 1280 x 640 social preview and a provenance manifest. It needs
only tracked archived figures and summaries; no GPU, checkpoints or downloads.
For a production-interface replay, use the separate [CPU smoke example](../minimal_replay/README.md).

## Read the evidence

- **P001 query 13 s / history 8 s:** 0 supported, 1 contradicted and 0 unknown
  reported assignments; at most 2 supported one-to-one associations among the
  existing features. This pair has low capacity under the fixed evaluator.
- **P001 query 16.000000512 s / history 8.500000256 s:** 7 supported, 29
  contradicted and 2 unknown reported assignments; the existing-feature capacity
  is 20. Available reference associations are not recovered model matches.
- Green/red/gray describe independent reference verdicts. Blue represents a
  reference-only oracle diagnostic; it is never an input to the model.
- Fewer than 20 supported matches fails an external utility diagnostic. It does
  not establish an operational pose-gate rejection or invalidate the revisit.

Full counts, timestamps, image/evidence hashes and selection context remain in
[the archived report](../../docs/archive/ldo-matching-diagnostics-report.md) and
[original figure manifest](../../docs/archive/ldo-matching-diagnostics-figures.json).
The generated manifest includes source and output hashes. Historical files remain
unchanged. Rendering library changes can change output bytes.

The original baseline is MegaLoc + SuperPoint/LightGlue at confidence 0.3 with
1,024 keypoints. This walkthrough needs no inference hardware; the original
experiment runtime is recorded in its historical evidence. TartanAir images retain
their dataset terms; see [licensing](../../docs/licensing.md).
