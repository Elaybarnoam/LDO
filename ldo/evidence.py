"""Persist model-produced features and assignments, never recompute matching."""

from pathlib import Path

import numpy as np

from .artifacts import sha256, write_json
from .contracts import KeyframeInput, LocalFeatures, LoopProposalBatch


class EvidenceWriter:
    def __init__(self, root: Path, manifest: dict) -> None:
        self.root = root
        root.mkdir(parents=True, exist_ok=False)
        self.manifest = {
            "source": manifest["variant"],
            "coordinates": "original_raw_sensor_pixels",
            "model_manifest": manifest,
            "exports": {},
            "pairs": {},
        }

    def _features(self, frame: KeyframeInput, features: LocalFeatures) -> None:
        name = f"{frame.timestamp_ns}_cam0.npz"
        destination = self.root / name
        if name in self.manifest["exports"]:
            with np.load(destination, allow_pickle=False) as saved:
                if not np.array_equal(saved["points"], features.points):
                    raise ValueError("Re-extracted feature IDs changed within this run")
            return
        np.savez_compressed(
            destination,
            points=features.points,
            image_size=np.asarray(features.image_size, dtype=np.int64),
        )
        self.manifest["exports"][name] = {
            "sha256": sha256(destination),
            "image_sha256": sha256(frame.image_reference),
            "family": features.family,
            "fingerprint": features.fingerprint,
        }

    def append(self, batch: LoopProposalBatch) -> None:
        self._features(batch.query, batch.query_features)
        for candidate in batch.candidates:
            self._features(candidate.historical, candidate.historical_features)
            name = f"pair_{batch.query.timestamp_ns}_{candidate.historical.timestamp_ns}.npz"
            destination = self.root / name
            if destination.exists():
                raise ValueError("Duplicate correspondence pair in evidence")
            np.savez_compressed(
                destination, indices=candidate.matches.indices, scores=candidate.matches.scores
            )
            self.manifest["pairs"][name] = {
                "sha256": sha256(destination),
                "score_definition": candidate.matches.score_definition,
            }

    def finalize(self) -> None:
        write_json(self.root / "manifest.json", self.manifest)
