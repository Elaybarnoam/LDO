"""Compatible LightGlue assignments; confidence is not a loop probability."""

import numpy as np
import torch
from lightglue import LightGlue

from ..contracts import CorrespondenceBatch, LocalFeatures


class LightGlueMatcher:
    def __init__(self, device: torch.device, family: str, threshold: float) -> None:
        if family != "superpoint":
            raise ValueError("This adapter requires a SuperPoint-compatible checkpoint")
        self.device = device
        self.family = family
        self.model = LightGlue(features=family, filter_threshold=threshold).eval().to(device)

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
