"""SuperPoint observations kept in original camera pixels and CPU memory."""

import torch
from lightglue import SuperPoint

from .local import ImageExtractor


class SuperPointExtractor(ImageExtractor):
    family = "superpoint"

    def __init__(
        self,
        device: torch.device,
        maximum_keypoints: int,
        fingerprint: str,
        resize: int | None = None,
    ) -> None:
        super().__init__(
            SuperPoint(max_num_keypoints=maximum_keypoints),
            device,
            self.family,
            fingerprint,
            resize,
        )
