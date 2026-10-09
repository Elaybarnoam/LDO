"""Input-only adapter: saved learned pixel pairs into unchanged XYZ preparation."""

import hashlib
import json
from pathlib import Path

import cv2
import numpy as np


class SavedCorrespondences:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.manifest = json.loads((self.root / "manifest.json").read_text(encoding="utf-8"))
        if self.manifest["coordinates"] != "original_raw_sensor_pixels":
            raise ValueError("XYZ input adapter requires original camera pixels")
        self.source = self.manifest["source"]

    def _read(self, name: str, section: str) -> bytes:
        data = (self.root / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != self.manifest[section][name]["sha256"]:
            raise ValueError(f"Saved learned evidence differs from manifest: {name}")
        return data

    def features(self, image: Path):
        name = f"{image.stem}_cam0.npz"
        self._read(name, "exports")
        if (
            hashlib.sha256(image.read_bytes()).hexdigest()
            != self.manifest["exports"][name]["image_sha256"]
        ):
            raise ValueError("Learned feature source image differs from manifest")
        with np.load(self.root / name, allow_pickle=False) as data:
            points, size = data["points"].astype(float), tuple(map(int, data["image_size"]))
        if points.shape != (len(points), 2) or not np.isfinite(points).all():
            raise ValueError("Invalid learned observation coordinates")
        if np.any(points < 0) or np.any(points >= np.asarray(size)):
            raise ValueError("Learned observations are outside original image")
        return points, None, size

    def assignments(self, query: Path, history: Path, query_count: int, history_count: int):
        name = f"pair_{query.stem}_{history.stem}.npz"
        self._read(name, "pairs")
        with np.load(self.root / name, allow_pickle=False) as data:
            indices, scores = data["indices"], data["scores"]
        if (
            indices.dtype != np.int64
            or indices.shape != (len(scores), 2)
            or not np.isfinite(scores).all()
        ):
            raise ValueError("Invalid learned correspondence assignments")
        if np.any(indices < 0) or (
            len(indices)
            and (indices[:, 0].max() >= query_count or indices[:, 1].max() >= history_count)
        ):
            raise ValueError("Learned correspondence IDs outside saved features")
        if any(len(np.unique(indices[:, column])) != len(indices) for column in (0, 1)):
            raise ValueError("Duplicate learned assignment IDs")
        # cv2.DMatch carries indices through existing preparation. Its distance
        # is only a compatibility placeholder, removed from learned evidence.
        matches = [cv2.DMatch(int(q), int(h), 0.0) for q, h in indices]
        metadata = {
            (int(q), int(h)): {
                "matcher_score": float(score),
                "matcher_score_definition": self.manifest["pairs"][name]["score_definition"],
                "feature_source": self.source,
            }
            for (q, h), score in zip(indices, scores, strict=True)
        }
        return matches, metadata
