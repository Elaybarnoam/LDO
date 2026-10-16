"""Exact normalized cosine retrieval with causal temporal eligibility."""

import numpy as np

from ..contracts import FloatArray, KeyframeInput


class CosineIndex:
    def __init__(self, dimension: int, fingerprint: str) -> None:
        if dimension < 1:
            raise ValueError("Descriptor dimension must be positive")
        self.dimension = dimension
        self.fingerprint = fingerprint
        self.frames: list[KeyframeInput] = []
        self._descriptors = np.empty((64, dimension), dtype=np.float32)
        self._timestamps: list[int] = []

    def _validate(self, descriptor: FloatArray, fingerprint: str) -> None:
        if fingerprint != self.fingerprint:
            raise ValueError("Descriptor fingerprint differs from historical index")
        if descriptor.shape != (self.dimension,) or not np.isfinite(descriptor).all():
            raise ValueError("Invalid global descriptor")
        if not np.isclose(np.linalg.norm(descriptor), 1, atol=1e-4):
            raise ValueError("Cosine index requires normalized descriptors")

    def query(
        self,
        descriptor: FloatArray,
        fingerprint: str,
        timestamp_ns: int,
        exclusion_ns: int,
        top_k: int,
    ) -> tuple[int, list[tuple[KeyframeInput, float]]]:
        self._validate(descriptor, fingerprint)
        if top_k < 1 or exclusion_ns < 1:
            raise ValueError("Invalid retrieval budget or exclusion")
        # Frames are chronological, so eligible history is a contiguous prefix.
        from bisect import bisect_right

        eligible = bisect_right(self._timestamps, timestamp_ns - exclusion_ns)
        if not eligible:
            return 0, []
        scores = np.clip(self._descriptors[:eligible] @ descriptor, -1.0, 1.0)
        order = np.lexsort((np.asarray(self._timestamps[:eligible], dtype=np.int64), -scores))[
            :top_k
        ]
        return eligible, [(self.frames[int(i)], float(scores[i])) for i in order]

    def insert(self, frame: KeyframeInput, descriptor: FloatArray, fingerprint: str) -> None:
        self._validate(descriptor, fingerprint)
        if self._timestamps and frame.timestamp_ns <= self._timestamps[-1]:
            raise ValueError("Index insertion must be strictly chronological")
        count = len(self.frames)
        if count == len(self._descriptors):
            expanded = np.empty((count * 2, self.dimension), dtype=np.float32)
            expanded[:count] = self._descriptors
            self._descriptors = expanded
        self._descriptors[count] = descriptor
        self.frames.append(frame)
        self._timestamps.append(frame.timestamp_ns)

    @property
    def bytes_used(self) -> int:
        return self._descriptors.nbytes
