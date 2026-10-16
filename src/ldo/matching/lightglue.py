"""Compatible LightGlue assignments; confidence is not a loop probability."""

from pathlib import Path

import numpy as np
import torch
from lightglue import LightGlue

from ..contracts import CorrespondenceBatch, LocalFeatures


class LightGlueMatcher:
    def __init__(
        self,
        device: torch.device,
        family: str,
        threshold: float,
        *,
        checkpoint: Path | None = None,
        checkpoint_sha256: str | None = None,
        full_depth: bool = False,
    ) -> None:
        if family not in {"superpoint", "aliked"}:
            raise ValueError("This adapter requires a supported compatible checkpoint")
        if checkpoint is not None and family != "superpoint":
            raise ValueError("Adapted checkpoint is only compatible with SuperPoint")
        self.device = device
        self.family = family
        settings = (
            {"depth_confidence": -1, "width_confidence": -1, "flash": False, "mp": False}
            if full_depth
            else {}
        )
        self.model = LightGlue(features=family, filter_threshold=threshold, **settings).eval()
        if checkpoint is not None:
            from ..artifacts import sha256

            if not full_depth or sha256(checkpoint) != checkpoint_sha256:
                raise ValueError("Adapted checkpoint integrity or full-depth requirement failed")
            self.model.load_state_dict(
                torch.load(checkpoint, map_location="cpu", weights_only=True), strict=True
            )
        self.model.to(device)

    def _tensors(self, features: LocalFeatures) -> dict[str, torch.Tensor]:
        return {
            "keypoints": torch.tensor(features.points, device=self.device)[None],
            "descriptors": torch.tensor(features.descriptors, device=self.device)[None],
            "image_size": torch.tensor(features.image_size, device=self.device)[None],
        }

    @torch.inference_mode()
    def match(self, query: LocalFeatures, history: LocalFeatures) -> CorrespondenceBatch:
        if (
            query.family != self.family
            or history.family != self.family
            or query.fingerprint != history.fingerprint
        ):
            raise ValueError("Incompatible local descriptor families or checkpoints")
        if not len(query.points) or not len(history.points):
            return CorrespondenceBatch(
                np.empty((0, 2), dtype=np.int64),
                np.empty(0, np.float32),
                "lightglue_matchability_assignment",
            )
        output = self.model({"image0": self._tensors(query), "image1": self._tensors(history)})
        return CorrespondenceBatch(
            output["matches"][0].cpu().numpy().astype(np.int64),
            output["scores"][0].float().cpu().numpy(),
            "lightglue_matchability_assignment",
        )

    def close(self) -> None:
        self.model.cpu()
