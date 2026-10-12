"""Pinned upstream EfficientLoFTR; partner-dependent points stay pair-local."""

import json
import sys
from copy import deepcopy
from pathlib import Path

from ldo.artifacts import identity, sha256

from .image_pairs import select_matches


class EfficientLoFTRMatcher:
    def __init__(
        self, root: Path, device: str = "cuda", threshold: float = 0.2, budget: int = 1024
    ):
        import torch
        from safetensors.torch import load_file

        manifest = json.loads((root / "manifest.json").read_text())
        for filename, expected in manifest["artifacts"].items():
            if sha256(root / filename) != expected:
                raise ValueError(f"EfficientLoFTR model/source changed: {filename}")
        repository = root / "EfficientLoFTR"
        if "src" in sys.modules:
            locations = list(getattr(sys.modules["src"], "__path__", ()))
            if not locations or not all(
                Path(path).resolve().is_relative_to(repository) for path in locations
            ):
                raise RuntimeError("Another package owns the upstream 'src' namespace")
        if str(repository) not in sys.path:
            sys.path.insert(0, str(repository))
        from src.loftr import LoFTR, full_default_cfg, reparameter

        self.device, self.threshold, self.budget = torch.device(device), threshold, budget
        if device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("Configured CUDA device is unavailable")
        config = deepcopy(full_default_cfg)
        if config["match_coarse"]["thr"] != 0.2 or config["match_coarse"]["skip_softmax"]:
            raise ValueError("Expected the pinned full default configuration")
        self.model = LoFTR(config=config)
        self.model.load_state_dict(load_file(str(root / "eloftr_outdoor.safetensors")), strict=True)
        self.model = reparameter(self.model).eval().to(self.device)
        self.fingerprint = identity(
            {
                "manifest": manifest,
                "config": config,
                "threshold": threshold,
                "budget": budget,
                "precision": "fp32",
                "resize": None,
            }
        )

    def match_images(self, query: Path, history: Path):
        import cv2
        import torch

        images = [cv2.imread(str(path), cv2.IMREAD_GRAYSCALE) for path in (query, history)]
        if any(image is None for image in images):
            raise ValueError("Cannot decode an image pair")
        if any(min(image.shape) < 64 or any(size % 32 for size in image.shape) for image in images):
            raise ValueError("Native EfficientLoFTR inputs must be at least 64 and divisible by 32")
        batch = {
            f"image{i}": torch.from_numpy(image).to(self.device, dtype=torch.float32)[None, None]
            / 255
            for i, image in enumerate(images)
        }
        with torch.inference_mode():
            self.model(batch)
        return select_matches(
            batch["mkpts0_f"].float().cpu().numpy(),
            batch["mkpts1_f"].float().cpu().numpy(),
            batch["mconf"].float().cpu().numpy(),
            self.threshold,
            self.budget,
        )

    def close(self):
        self.model.cpu()
