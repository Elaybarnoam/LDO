"""Install the pinned pretrained GPU stereo backend in a dedicated Linux runtime."""

import hashlib
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

SOURCE = Path("/opt/loop-detector/Fast-FoundationStereo")
REVISION = "476f4249561f7c79ca707326954f9255643412a6"
MODEL_REVISION = "53a84e28a368f37e699776250215fcb450d6a109"
MODEL_SHA256 = "2c79bbb274dc0aef687a8732b987077e9e3aa26ff9dd653141cda48c57dad5d3"
PYTHON = Path("/opt/loop-detector/fast-stereo-env/bin/python")
UV = Path.home() / ".local/bin/uv"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def record():
    revision = subprocess.check_output(
        ["git", "-C", str(SOURCE), "rev-parse", "HEAD"], text=True
    ).strip()
    if revision != REVISION:
        raise ValueError("Stereo source revision differs from pin")
    weights = SOURCE / "weights/nvidia-c-fast"
    checkpoint = weights / "model.onnx"
    if digest(checkpoint) != MODEL_SHA256:
        raise ValueError("Stereo checkpoint SHA256 differs from published NVIDIA artifact")
    paths = [
        *SOURCE.glob("core/**/*.py"),
        SOURCE / "Utils.py",
        weights / "cfg.yaml",
        checkpoint,
        Path(__file__).with_name("stereo-runtime.lock"),
    ]
    manifest = {
        "source_url": "https://github.com/NVlabs/Fast-FoundationStereo",
        "revision": revision,
        "model_url": "https://huggingface.co/nvidia/c-fast-foundationstereo",
        "model_revision": MODEL_REVISION,
        "python": str(PYTHON),
        "artifacts": {str(p): digest(p) for p in paths},
    }
    (SOURCE / "ldo-install.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"installed": True, "revision": revision, "checkpoint_sha256": MODEL_SHA256}))


def main():
    if sys.platform != "linux":
        raise RuntimeError("Run this installer in the configured WSL Ubuntu environment")
    if "--record-existing" not in sys.argv:
        if not SOURCE.exists():
            subprocess.run(
                ["git", "clone", "https://github.com/NVlabs/Fast-FoundationStereo", str(SOURCE)],
                check=True,
            )
        subprocess.run(["git", "-C", str(SOURCE), "checkout", REVISION], check=True)
        if not PYTHON.exists():
            subprocess.run(
                [str(UV), "venv", str(PYTHON.parent.parent), "--python", "3.12"], check=True
            )
        subprocess.run(
            [
                str(UV),
                "pip",
                "install",
                "--python",
                str(PYTHON),
                "-r",
                str(Path(__file__).with_name("stereo-runtime.lock")),
                "--extra-index-url",
                "https://download.pytorch.org/whl/cu128",
                "--index-strategy",
                "unsafe-best-match",
            ],
            check=True,
        )
        folder = SOURCE / "weights/nvidia-c-fast"
        folder.mkdir(parents=True, exist_ok=True)
        for name in ("onnx/c_fast_foundationstereo_bp2_dynbatch_dynhw.onnx", "cfg.yaml"):
            url = f"https://huggingface.co/nvidia/c-fast-foundationstereo/resolve/{MODEL_REVISION}/{name}"
            urllib.request.urlretrieve(
                url, folder / ("model.onnx" if name.endswith(".onnx") else name)
            )
    record()


if __name__ == "__main__":
    main()
