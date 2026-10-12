"""ALIKED observations use the same original-pixel contract as SuperPoint."""

from lightglue import ALIKED

from .local import ImageExtractor


class AlikedExtractor(ImageExtractor):
    family = "aliked"

    def __init__(self, device, maximum_keypoints, fingerprint, resize=None):
        super().__init__(
            ALIKED(model_name="aliked-n16", max_num_keypoints=maximum_keypoints),
            device,
            self.family,
            fingerprint,
            resize,
        )
