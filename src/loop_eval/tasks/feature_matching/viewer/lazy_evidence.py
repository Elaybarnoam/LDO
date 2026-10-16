"""Bounded-memory access to large per-feature JSONL evidence files."""

import hashlib
import json
from collections import OrderedDict
from pathlib import Path

import numpy as np


class PairStore:
    def __init__(self, path: Path, capacity: int = 3) -> None:
        self.path = path
        self.capacity = capacity
        self.cache: OrderedDict[int, dict] = OrderedDict()
        self.excluded_count = 0

    def headers(self):
        with self.path.open("rb") as stream:
            while True:
                offset = stream.tell()
                line = stream.readline()
                if not line:
                    break
                pair = json.loads(line)
                if pair.get("pose_evidence", {}).get("available") is not True:
                    self.excluded_count += 1
                    continue
                stereo = pair.get("stereo", {})
                if "feature_results" not in stereo:
                    yield pair
                    continue
                codes = {"supported": 1, "contradicted": 2, "untestable": 3}
                verdicts = np.fromiter(
                    (codes[p["verdict"]] for p in stereo["feature_results"]), dtype=np.uint8
                )
                compact = {k: v for k, v in pair.items() if k not in {"stereo", "feature_matches"}}
                compact["stereo"] = {
                    k: v for k, v in stereo.items() if k not in {"feature_results", "landmarks"}
                }
                compact["stereo"]["feature_results"] = []  # Marks the feature-level schema.
                compact.update(
                    _offset=offset,
                    _line_sha256=hashlib.sha256(line).hexdigest(),
                    _feature_verdicts=verdicts,
                )
                yield compact

    def load(self, header: dict) -> dict:
        if "_offset" not in header:
            return header
        offset = header["_offset"]
        if offset in self.cache:
            self.cache.move_to_end(offset)
            return self.cache[offset]
        with self.path.open("rb") as stream:
            stream.seek(offset)
            line = stream.readline()
        if hashlib.sha256(line).hexdigest() != header["_line_sha256"]:
            raise ValueError("Pair evidence changed since its index was loaded")
        pair = json.loads(line)
        self.cache[offset] = pair
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)
        return pair
