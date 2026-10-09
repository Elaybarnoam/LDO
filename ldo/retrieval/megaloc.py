"""Pinned pretrained MegaLoc inference, with official preprocessing."""

import importlib.util
from pathlib import Path

import torch
from PIL import Image
from safetensors.torch import load_file
from torchvision import transforms

from ..artifacts import identity
from ..contracts import FloatArray


class MegaLocEncoder:
    dimension = 8448

    def __init__(self, root: Path, device: torch.device, manifest: dict) -> None:
        source = root / "MegaLoc/megaloc_model.py"
        spec = importlib.util.spec_from_file_location("_ldo_pinned_megaloc", source)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load MegaLoc source: {source}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.device = device
        self.model = module.MegaLoc()
        self.model.load_state_dict(load_file(str(root / "weights/megaloc.safetensors")))
        self.model.eval().to(device)
        self.transform = transforms.Compose(
            [
                transforms.ToTensor(),
                transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
                transforms.Resize([322, 322], antialias=True),
            ]
        )
        self.fingerprint = identity(
            {
                "adapter": "megaloc-v1",
                "dimension": self.dimension,
                "preprocessing": "official_rgb_imagenet_322",
                "artifacts": manifest["artifacts"],
            }
        )

    @torch.inference_mode()
    def encode(self, image: Path) -> FloatArray:
        with Image.open(image) as pixels:
            tensor = self.transform(pixels.convert("RGB"))[None].to(self.device)
        descriptor = self.model(tensor)[0].float().cpu().numpy()
        return descriptor

    def close(self) -> None:
        self.model.cpu()
