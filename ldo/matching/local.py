"""Common image extraction; upstream resize maps points back to sensor pixels."""

from pathlib import Path

import cv2
import torch

from ..contracts import LocalFeatures


class ImageExtractor:
    def __init__(self, model, device, family, fingerprint, resize=None):
        self.model = model.eval().to(device)
        self.device, self.family, self.fingerprint, self.resize = (
            device,
            family,
            fingerprint,
            resize,
        )

    @torch.inference_mode()
    def extract(self, path: Path) -> LocalFeatures:
        image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise ValueError(f"Cannot decode keyframe: {path}")
        tensor = torch.from_numpy(image).to(self.device, dtype=torch.float32)[None] / 255
        features = self.model.extract(tensor, resize=self.resize)
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
