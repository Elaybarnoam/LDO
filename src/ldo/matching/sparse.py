"""Compose a compatible extractor and sparse assignment matcher."""

from pathlib import Path
from typing import Protocol

from ..contracts import CorrespondenceBatch, LocalFeatures


class Extractor(Protocol):
    def extract(self, image: Path) -> LocalFeatures: ...
    def close(self) -> None: ...


class Matcher(Protocol):
    def match(self, query: LocalFeatures, history: LocalFeatures) -> CorrespondenceBatch: ...
    def close(self) -> None: ...


class SparsePairEngine:
    def __init__(self, extractor: Extractor, matcher: Matcher, fingerprint: str) -> None:
        self.extractor = extractor
        self.matcher = matcher
        self.fingerprint = fingerprint

    def extract(self, image: Path) -> LocalFeatures:
        return self.extractor.extract(image)

    def match(self, query: LocalFeatures, history: LocalFeatures) -> CorrespondenceBatch:
        result = self.matcher.match(query, history)
        if len(result.indices) and (
            result.indices[:, 0].max() >= len(query.points)
            or result.indices[:, 1].max() >= len(history.points)
        ):
            raise ValueError("Matcher returned out-of-range feature IDs")
        return result

    def close(self) -> None:
        self.matcher.close()
        self.extractor.close()
