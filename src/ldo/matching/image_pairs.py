"""Replaceable image-pair matching interface with original subpixel coordinates."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np


@dataclass(frozen=True, slots=True)
class PixelCorrespondences:
    query_points: np.ndarray
    historical_points: np.ndarray
    scores: np.ndarray
    score_definition: str

    def __post_init__(self):
        n = len(self.scores)
        if self.query_points.shape != (n, 2) or self.historical_points.shape != (n, 2):
            raise ValueError("Pixel correspondence arrays must align")
        if self.scores.shape != (n,) or any(
            not np.isfinite(a).all()
            for a in (self.query_points, self.historical_points, self.scores)
        ):
            raise ValueError("Pixel correspondences must be finite")
        for points in (self.query_points, self.historical_points):
            if len(np.unique(points, axis=0)) != n:
                raise ValueError("A pixel endpoint cannot be reused")
        for array in (self.query_points, self.historical_points, self.scores):
            array.flags.writeable = False


class ImagePairMatcher(Protocol):
    fingerprint: str

    def match_images(self, query: Path, history: Path) -> PixelCorrespondences: ...
    def close(self) -> None: ...


def select_matches(q, h, scores, threshold: float, budget: int) -> PixelCorrespondences:
    """Confidence ranking and exact endpoint uniqueness; reference-free selection."""
    q, h, scores = np.asarray(q), np.asarray(h), np.asarray(scores)
    if q.shape != h.shape or q.shape != (len(scores), 2) or scores.shape != (len(q),):
        raise ValueError("Unaligned model match output")
    if not 0 <= threshold <= 1 or type(budget) is not int or budget < 1:
        raise ValueError("Invalid confidence threshold or match budget")
    if any(not np.isfinite(a).all() for a in (q, h, scores)):
        raise ValueError("Model produced nonfinite correspondence evidence")
    if np.any((scores < 0) | (scores > 1)):
        raise ValueError("Full EfficientLoFTR confidence must be in [0, 1]")
    order = np.argsort(-scores, kind="stable")
    selected, seen_q, seen_h = [], set(), set()
    for index in order:
        if scores[index] <= threshold:
            break
        a, b = tuple(q[index]), tuple(h[index])
        if a in seen_q or b in seen_h:
            continue
        selected.append(index)
        seen_q.add(a)
        seen_h.add(b)
        if len(selected) == budget:
            break
    chosen = np.asarray(selected, np.int64)
    return PixelCorrespondences(
        q[chosen].astype(np.float32),
        h[chosen].astype(np.float32),
        scores[chosen].astype(np.float32),
        "efficientloftr_full_coarse_dual_softmax",
    )
