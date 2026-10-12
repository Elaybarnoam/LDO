"""Install additional models and fresh test references, preserving old roots."""

import json
import shutil
from pathlib import Path

import yaml

from ldo.artifacts import sha256, verify_install, write_json
from tasks.reference_depth_v2.assets import fetch
from tasks.reference_depth_v2.assets import install as install_semantics
from tasks.reference_geometry.install import install
from tasks.reference_geometry.workflow import prepare

ROOT = Path(__file__).resolve().parents[4]
CONFIG = Path(__file__).with_name("config.yaml")
ALIKED_REVISION = "683d7c65197395c0b3f01ebe76e1084a27e73a65"


def model_assets(settings):
    root = Path(settings["model_root"])
    if (root / "matching-assets.json").exists():
        return verify_install(root)
    base = Path(yaml.safe_load((ROOT / settings["baseline"]).read_text())["model_root"])
    original = verify_install(base)
    if not root.exists():
        shutil.copytree(base, root)
    cache = root / "torch/checkpoints"
    sources = {
        "aliked-n16.pth": f"https://raw.githubusercontent.com/Shiaoming/ALIKED/{ALIKED_REVISION}/models/aliked-n16.pth",
        "aliked_lightglue_v0-1_arxiv.pth": "https://github.com/cvg/LightGlue/releases/download/v0.1_arxiv/aliked_lightglue.pth",
    }
    hashes = {name: fetch(url, cache / name) for name, url in sources.items()}
    manifest = {
        **original,
        "artifacts": {
            **original["artifacts"],
            **{f"torch/checkpoints/{name}": value for name, value in hashes.items()},
        },
    }
    write_json(root / "manifest.json", manifest)
    write_json(
        root / "matching-assets.json",
        {
            "aliked_revision": ALIKED_REVISION,
            "urls": sources,
            "sha256": hashes,
            "base_manifest_sha256": sha256(base / "manifest.json"),
        },
    )
    print("Verified SuperPoint and ALIKED model assets", flush=True)
    return manifest


def main():
    settings = yaml.safe_load(CONFIG.read_text())
    output = Path(settings["artifact_root"])
    output.mkdir(parents=True, exist_ok=True)
    model_assets(settings)
    dataset = {
        **settings["test"],
        "archives": [
            "image_lcam_front.zip",
            "image_rcam_front.zip",
            "depth_lcam_front.zip",
            "imu.zip",
        ],
    }
    install(dataset)
    folder = Path(dataset["root"]) / dataset["environment"] / dataset["difficulty"]
    trajectories = sorted(
        p.name for p in folder.glob("P*") if (p / "pose_lcam_front.txt").is_file()
    )
    if not trajectories:
        raise ValueError("No test trajectories installed")
    source = json.loads((ROOT / settings["source_results"]).read_text())
    semantic_source = {
        "environments": [
            *source["environments"],
            {"environment": dataset["environment"], "task": {"manifest": {"dataset": dataset}}},
        ]
    }
    assets = install_semantics(semantic_source, Path(settings["asset_root"]))
    write_json(output / "semantic-assets.json", assets)
    reference = yaml.safe_load(
        (ROOT / "evaluation/src/tasks/reference_geometry/config.yaml").read_text()
    )
    reference.update(
        dataset={**dataset, "trajectories": trajectories},
        output=str(output / "test"),
        ldo_config=settings["baseline"],
    )
    config = output / "test-reference.yaml"
    encoded = yaml.safe_dump(reference, sort_keys=False)
    if config.exists() and config.read_text() != encoded:
        raise ValueError("Test reference selection changed")
    config.write_text(encoded)
    marker = output / "test-prepared.json"
    if marker.exists():
        item = json.loads(marker.read_text())
        if sha256(Path(item["root"]) / "manifest.json") != item["sha256"]:
            raise ValueError("Frozen test reference changed")
    else:
        root = prepare(reference, config)
        write_json(
            marker,
            {
                "root": str(root),
                "sha256": sha256(root / "manifest.json"),
                "configuration_sha256": sha256(config),
            },
        )
    print(f"Fresh test reference ready: {dataset['environment']} {trajectories}", flush=True)


if __name__ == "__main__":
    main()
