# Geometry failure review

Current evaluation requirement: use datasets with provided ground-truth depth
maps and reference camera poses. The current review uses TartanAir OldTownFall.

From the project root on Windows:

```powershell
.venv/Scripts/python.exe evaluation/view_geometry_failures.py
```

Open `evaluation/output/geometry-failures/index.html` in a browser. It is a
self-contained offline page. The builder reads existing artifacts through
`\\wsl.localhost\Ubuntu-24.04`; use `--distro` for another installed WSL name.
It verifies saved NPZ hashes and does not rerun inference or change verdicts.

- Left/right arrows: previous/next failed feature, crossing image-pair boundaries.
- Shift + left/right arrows: previous/next image pair.
- Dropdown: jump to an image pair.
- Red line: actual LDO correspondence.
- Cyan cross: where the current pixel projects into the historical image using
  reference depth and poses. Its dashed connection to the selected historical
  pixel shows the forward reprojection discrepancy.
- The numerical reprojection metric is the maximum of forward and reverse
  errors. It can exceed the forward error visible in the image.
- XYZ uses the saved tolerance `max(0.05 m, 0.005 * max(depths))`; reprojection
  tolerance is 3 px. Both checks must pass for support.
- A reference prediction outside the image or behind the camera has no visible
  cross. Its status appears below the images.
- Technical evidence and Copy retain feature IDs, coordinates, timestamps,
  residuals and provenance for discussion.

Scope: 363 contradicted matches across 27 image pairs, selected from the 30
pairs in the four weak-event diagnosis. This is not all benchmark failures.
Unknown matches are excluded. Reference projections are evaluator evidence,
not new model matches or a guarantee of visible, unoccluded feature identity.

The reviewer changes no model, retrieval, depth sampling or XYZ policy.
