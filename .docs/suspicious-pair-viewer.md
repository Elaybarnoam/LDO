# LDO candidate review

Current implementation: policy version 8 evaluates individual ORB correspondences without temporal RANSAC. See [feature XYZ evaluation](feature-xyz-evaluation.md). The earlier workflow below is retained as historical documentation.


## Launch

Run from the project root on Windows:

```powershell
uv run python evaluation/view_suspicious.py
uv run python evaluation/view_suspicious.py --group "not supported"
```

The viewer opens the latest completed benchmark evidence. It reads saved
ORB + DBoW2 candidates and does not rerun retrieval or change results.

Every displayed pair must have valid ground-truth poses at both timestamps.
The 95 missing-reference pairs from the earlier run are excluded from tabs
and counts. The header shows eligible and excluded totals. See
`evaluation-ground-truth-admission.md` for the mandatory admission rule.

## Layout

- Three candidate tabs with counts and an active indicator.
- Current image and historical image, with uncluttered feature overlays.
- Six-stage XYZ evaluation flow with observed values, saved thresholds,
  and a plain-language explanation of the decision.
- Selected-feature inspector with pixel coordinates, world XYZ estimates,
  uncertainty-weighted distance, and auxiliary reprojection errors.
- Clickable previous/next navigation and keyboard shortcuts.

Tabs, image panels, flow cards, inspector, and navigation buttons use rounded
corners. Technical flow cards show saved numerical observations and settings:
DBoW2 score, searched history, ORB/BoW counts and retrieval time; pose timestamp
errors and body-to-camera/world transform; stereo depth/parallax/reprojection
gates and pixel noise; the Mahalanobis formula and threshold; covariance noise
assumptions; XYZ agreement and all support/rejection thresholds.
Retrieval metadata is loaded from the hash-verified trace associated with the
saved checker provenance. Missing technical values display N/A. Selected
landmarks also expose the largest-axis three-sigma uncertainty radius.

### Candidate tabs

| Tab / key | Example count from an older retained run | Meaning |
| --- | ---: | --- |
| ORB + DBoW2 candidates / 1 | 1,540 | Returned candidate pairs admitted by the ground-truth prerequisite |
| XYZ supports / 2 | 489 | Sufficient world XYZ agreement |
| XYZ does not support / 3 | 1,051 | 0 rejected, 11 ambiguous, 1,040 insufficient stereo/XYZ evidence |

Lack of XYZ support is not proof that a candidate is incorrect. The third tab
always explains the actual reason. All groups originate from ORB + DBoW2
retrieval candidates, rather than final accepted ORB-SLAM3 loops.

### XYZ evaluation flow

1. **Retrieval:** candidate returned and retrieval rank.
2. **Temporal RANSAC:** raw, retained and rejected matches, fit status and thresholds.
3. **Reference poses:** availability and the saved timestamp tolerance.
4. **Stereo landmarks:** paired triangulated depths and usable world XYZ records.
5. **XYZ agreement:** passing landmarks out of all retained matches. Reprojection
   does not affect the XYZ-only classification.
6. **Pair decision:** supported, rejected, ambiguous, or insufficient evidence.

Policy version 7 has no cell/grid-coverage decision gate. A highlighted stage
explains whether a pair lacked poses/depth or had too few agreeing landmarks.
The overlay uses only post-RANSAC retained feature pairs. All lines are shown
by default; L toggles the selected-line view. Retained matches with unavailable
depth remain visible as untested (cyan), rather than failed (red).

No-support and ambiguous stages are amber; a genuine rejection is red.
Supported stages are green. The flow remains visible in every candidate tab.

### Feature colors

| Color | Meaning |
| --- | --- |
| Green | XYZ and reprojection pass |
| Orange | XYZ passes; reprojection fails |
| Purple | XYZ fails; reprojection passes |
| Red | Both fail |
| Cyan | Reconstructed 2D match; XYZ not evaluated |

Saved XYZ observations use the benchmark's exported upstream ORB features.
Pairs without usable world landmarks show their saved temporal ORB matches in
cyan. The viewer never extracts or matches replacement features. Cyan means
XYZ could not be evaluated; it is not a geometric rejection.

The copy button includes the ORB feature IDs and their saved numerical evidence.

## Version 4 support denominator

XYZ passing ratio is passing landmarks / all reported temporal ORB matches.
The flow shows both counts and ceil(match count × support ratio) as the required
count. Depth availability is separate. Earlier reports retain their saved policy.
