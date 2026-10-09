"""Chronological detector orchestration, independent of evaluation and SLAM."""

import time

from .contracts import (
    Candidate,
    GlobalEncoder,
    KeyframeInput,
    LoopProposalBatch,
    PairEngine,
    ProposalPolicy,
)
from .memory import FeatureCache
from .retrieval.index import CosineIndex


class Detector:
    def __init__(
        self,
        encoder: GlobalEncoder,
        engine: PairEngine,
        policy: ProposalPolicy,
        *,
        top_k: int = 5,
        exclusion_ns: int = 20_000_000_000,
        cache_size: int = 128,
    ) -> None:
        if type(top_k) is not int or not 1 <= top_k <= 100 or exclusion_ns < 1:
            raise ValueError("Invalid candidate budget or temporal exclusion")
        self.encoder, self.engine, self.policy = encoder, engine, policy
        self.top_k, self.exclusion_ns = top_k, exclusion_ns
        self.cache = FeatureCache(engine, cache_size)
        self.reset()

    def reset(self) -> None:
        if getattr(self, "_closed", False):
            raise RuntimeError("Cannot reset a closed detector")
        self.index = CosineIndex(self.encoder.dimension, self.encoder.fingerprint)
        self.cache.clear()
        self.policy.reset()
        self._session: str | None = None
        self._previous = -1
        self._ids: set[str] = set()
        self._closed = False
        self._failed = False

    def process_keyframe(self, frame: KeyframeInput) -> LoopProposalBatch:
        if self._closed or self._failed:
            raise RuntimeError("Detector is closed or failed; initialize a fresh instance")
        if frame.camera_id != "cam0":
            raise ValueError("This configuration consumes cam0 images")
        if type(frame.timestamp_ns) is not int or frame.timestamp_ns <= self._previous:
            raise ValueError("Keyframes must have strictly increasing integer timestamps")
        if frame.keyframe_id in self._ids or not frame.keyframe_id:
            raise ValueError("Duplicate or empty keyframe ID")
        if self._session is not None and frame.session_id != self._session:
            raise ValueError("Reset before changing detector sessions")
        if not frame.image_reference.is_file():
            raise ValueError(f"Missing image: {frame.image_reference}")
        started = time.perf_counter()
        try:
            descriptor = self.encoder.encode(frame.image_reference)
            encoded = time.perf_counter()
            eligible, ranked = self.index.query(
                descriptor,
                self.encoder.fingerprint,
                frame.timestamp_ns,
                self.exclusion_ns,
                self.top_k,
            )
            searched = time.perf_counter()
            query_features = self.cache.get(frame.image_reference)
            extracted = time.perf_counter()
            candidates = []
            for rank, (history, score) in enumerate(ranked, 1):
                historical_features = self.cache.get(history.image_reference)
                matches = self.engine.match(query_features, historical_features)
                candidates.append(Candidate(history, rank, score, matches, historical_features))
            decided = self.policy.apply(frame, tuple(candidates))
            matched = time.perf_counter()
            self.index.insert(frame, descriptor, self.encoder.fingerprint)
        except Exception:
            # Never continue with potentially partial state after inference failure.
            self._failed = True
            raise
        self._previous, self._session = frame.timestamp_ns, frame.session_id
        self._ids.add(frame.keyframe_id)
        return LoopProposalBatch(
            frame,
            query_features,
            decided,
            eligible,
            {
                "global_encoding": (encoded - started) * 1000,
                "retrieval": (searched - encoded) * 1000,
                "feature_extraction": (extracted - searched) * 1000,
                "pair_matching_and_policy": (matched - extracted) * 1000,
                "total": (time.perf_counter() - started) * 1000,
            },
        )

    def close(self) -> None:
        if self._closed:
            return
        try:
            self.engine.close()
        finally:
            self.encoder.close()
            self.cache.clear()
            self._closed = True
