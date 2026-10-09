"""Bounded CPU feature cache; representations never mix across adapters."""

from collections import OrderedDict
from pathlib import Path

from .contracts import LocalFeatures, PairEngine


class FeatureCache:
    def __init__(self, engine: PairEngine, capacity: int) -> None:
        if type(capacity) is not int or capacity < 1:
            raise ValueError("Feature cache capacity must be positive")
        self.engine = engine
        self.capacity = capacity
        self._items: OrderedDict[Path, LocalFeatures] = OrderedDict()
        self.hits = 0
        self.misses = 0

    def get(self, image: Path) -> LocalFeatures:
        image = image.resolve()
        if image in self._items:
            self.hits += 1
            self._items.move_to_end(image)
            return self._items[image]
        self.misses += 1
        features = self.engine.extract(image)
        if features.fingerprint != self.engine.fingerprint:
            raise ValueError("Feature representation differs from the configured engine")
        self._items[image] = features
        if len(self._items) > self.capacity:
            self._items.popitem(last=False)
        return features

    @property
    def bytes_used(self) -> int:
        return sum(
            f.points.nbytes + f.descriptors.nbytes + f.scores.nbytes for f in self._items.values()
        )

    def clear(self) -> None:
        self._items.clear()
