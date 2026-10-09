"""Install/check pinned inference sources and weights in the chosen runtime.

Run with the GPU environment's Python: python -m ldo.install --root PATH.
Python dependencies are managed separately by uv and the project lock file.
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.request import urlretrieve

from .artifacts import sha256, write_json


def install(root: Path) -> dict:
    from huggingface_hub import hf_hub_download

    root.mkdir(parents=True, exist_ok=True)
    pins = json.loads(Path(__file__).with_name("upstream.lock.json").read_text())
    for name, folder in (("megaloc", "MegaLoc"), ("lightglue", "LightGlue")):
        source = root / folder
        pin = pins[name]
        if not source.exists():
            subprocess.run(["git", "clone", pin["repository"], str(source)], check=True)
            subprocess.run(["git", "-C", str(source), "checkout", pin["revision"]], check=True)
        revision = subprocess.check_output(
            ["git", "-C", str(source), "rev-parse", "HEAD"], text=True
        ).strip()
        modified = subprocess.check_output(
            ["git", "-C", str(source), "diff", "HEAD", "--name-only"], text=True
        ).strip()
        if revision != pin["revision"] or modified:
            raise ValueError(f"Model source is not the clean pinned revision: {source}")
    weights = root / "weights"
    weights.mkdir(exist_ok=True)
    pin = pins["megaloc_weights"]
    checkpoint = weights / "megaloc.safetensors"
    if not checkpoint.exists():
        downloaded = hf_hub_download(
            repo_id=pin["repository"], revision=pin["revision"], filename=pin["filename"]
        )
        shutil.copyfile(downloaded, checkpoint)
    torch_cache = root / "torch/checkpoints"
    torch_cache.mkdir(parents=True, exist_ok=True)
    release = "https://github.com/cvg/LightGlue/releases/download/v0.1_arxiv"
    for remote, local in (
        ("superpoint_v1.pth", "superpoint_v1.pth"),
        ("superpoint_lightglue.pth", "superpoint_lightglue_v0-1_arxiv.pth"),
    ):
        destination = torch_cache / local
        if not destination.exists():
            temporary = destination.with_suffix(".download")
            urlretrieve(f"{release}/{remote}", temporary)
            temporary.replace(destination)
    files = [
        root / "MegaLoc/megaloc_model.py",
        root / "MegaLoc/LICENSE",
        checkpoint,
        *sorted((root / "LightGlue/lightglue").glob("*.py")),
        root / "LightGlue/LICENSE",
        *torch_cache.glob("*.pth"),
    ]
    artifacts = {str(path.relative_to(root)): sha256(path) for path in files}
    existing = root / "manifest.json"
    if existing.is_file():
        previous = json.loads(existing.read_text())
        if previous["artifacts"] != artifacts or previous["pins"] != pins:
            raise ValueError(
                "Installed artifacts changed; choose a new model root for a new revision"
            )
    manifest = {
        "pins": pins,
        "artifacts": artifacts,
        "python": sys.executable,
        "licenses": {
            "MegaLoc": "MIT",
            "LightGlue": "Apache-2.0",
            "SuperPoint": "Separate restrictive upstream research license",
        },
    }
    write_json(existing, manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("/opt/loop-detector/ldo-models"))
    args = parser.parse_args()
    manifest = install(args.root.resolve())
    print(json.dumps({"installed": True, "root": str(args.root), "pins": manifest["pins"]}))


if __name__ == "__main__":
    main()
