"""Validated configuration and adapter registry; no model branching in Detector."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import yaml

from .artifacts import identity, verify_install
from .contracts import GlobalEncoder, PairEngine, ProposalPolicy
from .detector import Detector
from .policies.proposal import RetrievalOrderPolicy


@dataclass(frozen=True, slots=True)
class DetectorConfig:
    variant: str
    model_root: Path
    device: str
    retrieval: str
    matching: str
    policy: str
    top_k: int
    exclusion_ns: int
    maximum_keypoints: int
    cache_size: int
    match_threshold: float
    seed: int


def load_config(path: Path) -> DetectorConfig:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ValueError("LDO config requires version 1")
    expected = {
        "version",
        "variant",
        "model_root",
        "device",
        "retrieval",
        "matching",
        "policy",
        "top_k",
        "temporal_exclusion_seconds",
        "maximum_keypoints",
        "cache_size",
        "match_threshold",
        "seed",
    }
    if set(data) != expected:
        raise ValueError(f"Unexpected/missing LDO configuration keys: {set(data) ^ expected}")
    for key in ("top_k", "maximum_keypoints", "cache_size", "seed"):
        if type(data[key]) is not int or data[key] < (0 if key == "seed" else 1):
            raise ValueError(f"Invalid integer setting: {key}")
    import math

    for key in ("match_threshold", "temporal_exclusion_seconds"):
        if type(data[key]) not in (int, float) or not math.isfinite(data[key]):
            raise ValueError(f"Invalid numeric setting: {key}")
    if (
        not 0 <= data["match_threshold"] <= 1
        or not 0 < data["temporal_exclusion_seconds"] <= 3600
        or data["top_k"] > 100
    ):
        raise ValueError("Invalid match threshold, exclusion or candidate budget")
    if data["device"] not in {"cuda", "cpu"}:
        raise ValueError("Specify cuda or cpu explicitly")
    for key in ("variant", "model_root", "retrieval", "matching", "policy"):
        if not isinstance(data[key], str) or not data[key]:
            raise ValueError(f"Invalid text setting: {key}")
    root = Path(data["model_root"]).expanduser()
    if not root.is_absolute():
        root = (path.parent / root).resolve()
    return DetectorConfig(
        data["variant"],
        root,
        data["device"],
        data["retrieval"],
        data["matching"],
        data["policy"],
        data["top_k"],
        round(data["temporal_exclusion_seconds"] * 1e9),
        data["maximum_keypoints"],
        data["cache_size"],
        float(data["match_threshold"]),
        data["seed"],
    )


EncoderFactory = Callable[[DetectorConfig, dict], GlobalEncoder]
EngineFactory = Callable[[DetectorConfig, dict], PairEngine]
PolicyFactory = Callable[[], ProposalPolicy]


def _megaloc(config: DetectorConfig, manifest: dict) -> GlobalEncoder:
    import torch

    from .retrieval.megaloc import MegaLocEncoder

    return MegaLocEncoder(config.model_root, torch.device(config.device), manifest)


def _sparse(config: DetectorConfig, manifest: dict) -> PairEngine:
    import lightglue
    import torch

    from .artifacts import sha256
    from .matching.lightglue import LightGlueMatcher
    from .matching.sparse import SparsePairEngine
    from .matching.superpoint import SuperPointExtractor

    for path in Path(lightglue.__file__).parent.glob("*.py"):
        expected = manifest["artifacts"].get(f"LightGlue/lightglue/{path.name}")
        if expected != sha256(path):
            raise ValueError(f"Installed LightGlue differs from pinned source: {path}")
    device = torch.device(config.device)
    fingerprint = identity(
        {
            "artifacts": manifest["artifacts"],
            "extractor": "superpoint",
            "maximum_keypoints": config.maximum_keypoints,
            "resize": None,
        }
    )
    return SparsePairEngine(
        SuperPointExtractor(device, config.maximum_keypoints, fingerprint),
        LightGlueMatcher(device, "superpoint", config.match_threshold),
        fingerprint,
    )


ENCODERS: dict[str, EncoderFactory] = {"megaloc": _megaloc}
ENGINES: dict[str, EngineFactory] = {"superpoint_lightglue": _sparse}
POLICIES: dict[str, PolicyFactory] = {"retrieval_order": RetrievalOrderPolicy}


def build_detector(config: DetectorConfig) -> tuple[Detector, dict]:
    for name, registry in (
        (config.retrieval, ENCODERS),
        (config.matching, ENGINES),
        (config.policy, POLICIES),
    ):
        if name not in registry:
            raise ValueError(f"Unregistered LDO adapter: {name}")
    import importlib.metadata

    import numpy as np
    import torch

    install = verify_install(config.model_root)
    if config.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("Configured CUDA device is unavailable; no silent CPU fallback")
    torch.hub.set_dir(str(config.model_root / "torch"))
    torch.manual_seed(config.seed)
    np.random.seed(config.seed)
    torch.set_num_threads(1)
    encoder = ENCODERS[config.retrieval](config, install)
    try:
        engine = ENGINES[config.matching](config, install)
        detector = Detector(
            encoder,
            engine,
            POLICIES[config.policy](),
            top_k=config.top_k,
            exclusion_ns=config.exclusion_ns,
            cache_size=config.cache_size,
        )
    except Exception:
        encoder.close()
        raise
    manifest = {
        "architecture": "LDO",
        "variant": config.variant,
        "installation": install,
        "representation_fingerprint": encoder.fingerprint,
        "matching_fingerprint": engine.fingerprint,
        "device": config.device,
        "seed": config.seed,
        "match_threshold": config.match_threshold,
        "maximum_keypoints": config.maximum_keypoints,
        "gpu": torch.cuda.get_device_name(0) if config.device == "cuda" else None,
        "packages": {
            name: importlib.metadata.version(name)
            for name in ("torch", "torchvision", "numpy", "lightglue", "safetensors")
        },
    }
    manifest["manifest_id"] = identity(manifest)
    return detector, manifest
