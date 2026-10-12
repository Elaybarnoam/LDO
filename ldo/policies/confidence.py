"""Image-derived candidate confidence; no reference geometry at inference."""

import json
from dataclasses import replace
from pathlib import Path

import numpy as np
from scipy.special import expit

FEATURE_NAMES = (
    "retrieval_score",
    "distance_from_best",
    "median_match_score",
    "mean_match_score",
    "log_match_count",
    "historical_match_fraction",
)


def candidate_vector(score, best_score, match_scores, historical_count):
    values = np.asarray(match_scores, dtype=float)
    return np.array(
        [
            score,
            score - best_score,
            np.median(values) if len(values) else 0.0,
            np.mean(values) if len(values) else 0.0,
            np.log1p(len(values)),
            len(values) / max(historical_count, 1),
        ],
        dtype=float,
    )


class CandidateConfidencePolicy:
    def __init__(self, parameters):
        if parameters.get("feature_names") != list(FEATURE_NAMES):
            raise ValueError("Candidate confidence feature schema differs")
        self.mean = np.asarray(parameters["mean"], float)
        self.scale = np.asarray(parameters["scale"], float)
        self.weights = np.asarray(parameters["weights"], float)
        self.bias = float(parameters["bias"])
        self.threshold = float(parameters["threshold"])
        if (
            any(a.shape != (len(FEATURE_NAMES),) for a in (self.mean, self.scale, self.weights))
            or any(not np.isfinite(a).all() for a in (self.mean, self.scale, self.weights))
            or np.any(self.scale <= 0)
            or not np.isfinite(self.bias)
            or not 0 <= self.threshold <= 1
        ):
            raise ValueError("Invalid candidate confidence parameters")

    @classmethod
    def from_file(cls, path):
        if path is None:
            raise ValueError("Candidate confidence requires an explicit parameter file")
        return cls(json.loads(Path(path).read_text()))

    def score(self, vector):
        return float(
            expit(((np.asarray(vector) - self.mean) / self.scale) @ self.weights + self.bias)
        )

    def apply(self, query, candidates):
        if not candidates:
            return ()
        best = max(c.retrieval_score for c in candidates)
        kept = [
            c
            for c in candidates
            if self.score(
                candidate_vector(
                    c.retrieval_score, best, c.matches.scores, len(c.historical_features.points)
                )
            )
            >= self.threshold
        ]
        return tuple(replace(c, rank=i) for i, c in enumerate(kept, 1))

    def reset(self):
        pass
