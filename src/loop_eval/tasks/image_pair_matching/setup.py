"""Convert the official checkpoint to tensor-only weights and record provenance."""

import json
import platform
import subprocess
from importlib.metadata import version
from pathlib import Path

from ldo.artifacts import sha256, write_json

REVISION = "07e9c1401e71e9c556b1fda9d86d060af36ba176"


def runtime() -> dict:
    import torch

    return {
        "python": platform.python_version(),
        "torch": torch.__version__,
        "cuda": torch.version.cuda,
        "gpu": torch.cuda.get_device_name(0),
        "packages": {
            name: version(name)
            for name in (
                "numpy",
                "scipy",
                "kornia",
                "einops",
                "loguru",
                "yacs",
                "pytorch-lightning",
                "safetensors",
                "joblib",
            )
        },
    }


def prepare(root: Path) -> dict:
    import torch
    from pytorch_lightning.callbacks import ModelCheckpoint
    from safetensors.torch import save_file

    repository = root / "EfficientLoFTR"
    head = subprocess.check_output(
        ["git", "-C", str(repository), "rev-parse", "HEAD"], text=True
    ).strip()
    if (
        head != REVISION
        or subprocess.check_output(
            ["git", "-C", str(repository), "status", "--porcelain", "--untracked-files=no"],
            text=True,
        ).strip()
    ):
        raise ValueError("Use the pinned, unmodified official EfficientLoFTR source")
    original = root / "eloftr_outdoor.ckpt"
    converted = root / "eloftr_outdoor.safetensors"
    marker = root / "manifest.json"
    if marker.exists():
        manifest = json.loads(marker.read_text())
        for name, expected in manifest["artifacts"].items():
            if sha256(root / name) != expected:
                raise ValueError("Previously installed EfficientLoFTR artifacts changed")
        if runtime() != manifest["runtime"]:
            raise ValueError("Previously recorded candidate runtime changed")
        return manifest
    unsafe = set(torch.serialization.get_unsafe_globals_in_checkpoint(original))
    if unsafe != {"pytorch_lightning.callbacks.model_checkpoint.ModelCheckpoint"}:
        raise ValueError(f"Unexpected checkpoint object types: {unsafe}")
    with torch.serialization.safe_globals([ModelCheckpoint]):
        checkpoint = torch.load(original, map_location="cpu", weights_only=True)
    state = {k: tensor.contiguous() for k, tensor in checkpoint["state_dict"].items()}
    if not all(isinstance(value, torch.Tensor) for value in state.values()):
        raise ValueError("Expected tensor-only model parameters")
    save_file(state, str(converted))
    files = [
        original,
        converted,
        repository / "LICENSE",
        repository / "README.md",
        *sorted((repository / "src").rglob("*.py")),
    ]
    manifest = {
        "repository": "https://github.com/zju3dv/EfficientLoFTR",
        "revision": REVISION,
        "checkpoint_url": "https://drive.google.com/uc?id=1jFy2JbMKlIp82541TakhQPaoyB5qDeic",
        "artifacts": {str(path.relative_to(root)): sha256(path) for path in files},
        "conversion": "Tensor-only safetensors; weights_only load with ModelCheckpoint class allowlisted",
        "runtime": runtime(),
        "license": "Project Registration License v1.0; research evaluation clause",
    }
    write_json(marker, manifest)
    return manifest
