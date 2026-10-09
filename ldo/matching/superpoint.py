"""SuperPoint observations kept in original camera pixels and CPU memory."""

from pathlib import Path

import cv2
import torch
from lightglue import SuperPoint

from ..contracts import LocalFeatures


class SuperPointExtractor:
    family = "superpoint"

    def __init__(self, device: torch.device, maximum_keypoints: int, fingerprint: str) -> None:
        self.device = device
        self.fingerprint = fingerprint
        self.model = SuperPoint(max_num_keypoints=maximum_keypoints).eval().to(device)

    @torch.inference_mode()
    def extract(self, path: Path) -> LocalFeatures:
        image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise ValueError(f"Cannot decode keyframe: {path}")
        tensor = torch.from_numpy(image).to(self.device, dtype=torch.float32)[None] / 255
        # No resize: local points always refer to the raw sensor image.
        features = self.model.extract(tensor, resize=None)
        return LocalFeatures(
            features["keypoints"][0].float().cpu().numpy(),
            features["descriptors"][0].float().cpu().numpy(),
            features["keypoint_scores"][0].float().cpu().numpy(),
            (image.shape[1], image.shape[0]),
            self.family,
            self.fingerprint,
        )

    def close(self) -> None:
        self.model.cpu()
