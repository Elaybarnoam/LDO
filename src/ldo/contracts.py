"""Typed, model-independent observations and detection results."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float32]
IndexArray = NDArray[np.int64]


@dataclass(frozen=True, slots=True)
class KeyframeInput:
    keyframe_id: str
    timestamp_ns: int
    image_reference: Path
    session_id: str = "default"
    camera_id: str = "cam0"


@dataclass(frozen=True, slots=True)
class LocalFeatures:
    points: FloatArray
    descriptors: FloatArray
    scores: FloatArray
    image_size: tuple[int, int]
    family: str
    fingerprint: str

    def __post_init__(self) -> None:
        count = len(self.points)
        if self.points.shape != (count, 2) or self.descriptors.ndim != 2:
            raise ValueError("Invalid local feature dimensions")
        if len(self.descriptors) != count or self.scores.shape != (count,):
            raise ValueError("Local feature lengths differ")
        if not all(np.isfinite(a).all() for a in (self.points, self.descriptors, self.scores)):
            raise ValueError("Nonfinite local features")
        width, height = self.image_size
        if width <= 0 or height <= 0 or np.any(self.points < 0):
            raise ValueError("Invalid image size or feature coordinates")
        if np.any(self.points[:, 0] >= width) or np.any(self.points[:, 1] >= height):
            raise ValueError("Features must use original image pixels")
        for array in (self.points, self.descriptors, self.scores):
            array.flags.writeable = False


@dataclass(frozen=True, slots=True)
class CorrespondenceBatch:
    indices: IndexArray
    scores: FloatArray
    score_definition: str

    def __post_init__(self) -> None:
        if self.indices.shape != (len(self.scores), 2) or self.indices.dtype != np.int64:
            raise ValueError("Correspondences require integer index pairs")
        if np.any(self.indices < 0) or not np.isfinite(self.scores).all():
            raise ValueError("Invalid correspondence indices or scores")
        for column in (0, 1):
            if len(np.unique(self.indices[:, column])) != len(self.indices):
                raise ValueError("Sparse assignments must be one-to-one")
        self.indices.flags.writeable = False
        self.scores.flags.writeable = False


@dataclass(frozen=True, slots=True)
class Candidate:
    historical: KeyframeInput
    rank: int
    retrieval_score: float
    matches: CorrespondenceBatch
    historical_features: LocalFeatures
    sequence_support: int = 0


@dataclass(frozen=True, slots=True)
class LoopProposalBatch:
    query: KeyframeInput
    query_features: LocalFeatures
    candidates: tuple[Candidate, ...]
    eligible_history_count: int
    timings_ms: dict[str, float] = field(default_factory=dict)
    status: str = "completed"


class GlobalEncoder(Protocol):
    fingerprint: str
    dimension: int

    def encode(self, image: Path) -> FloatArray: ...
    def close(self) -> None: ...


class PairEngine(Protocol):
    fingerprint: str

    def extract(self, image: Path) -> LocalFeatures: ...
    def match(self, query: LocalFeatures, history: LocalFeatures) -> CorrespondenceBatch: ...
    def close(self) -> None: ...


class ProposalPolicy(Protocol):
    def apply(
        self, query: KeyframeInput, candidates: tuple[Candidate, ...]
    ) -> tuple[Candidate, ...]: ...
    def reset(self) -> None: ...
