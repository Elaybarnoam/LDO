"""Validated configuration and adapter registry; no model branching in Detector."""

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import yaml

from .artifacts import identity, sha256, verify_install
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
    policy_parameters: Path | None = None
    matcher_checkpoint: Path | None = None
    matcher_checkpoint_sha256: str | None = None
    matcher_full_depth: bool = False
    feature_resize: int | None = None


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
    optional = {
        "policy_parameters",
        "matcher_checkpoint",
        "matcher_checkpoint_sha256",
        "matcher_full_depth",
        "feature_resize",
    }
    if set(data) - optional != expected:
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
    root = Path(os.environ.get("LDO_MODEL_ROOT", data["model_root"])).expanduser()
    if not root.is_absolute():
        root = (path.parent / root).resolve()

    def optional_path(key):
        value = data.get(key)
        if value is None:
            return None
        if not isinstance(value, str) or not value:
            raise ValueError(f"Invalid path: {key}")
        target = Path(value).expanduser()
        return target if target.is_absolute() else (path.parent / target).resolve()

    if type(data.get("matcher_full_depth", False)) is not bool:
        raise ValueError("matcher_full_depth must be boolean")
    resize = data.get("feature_resize")
    if resize is not None and (type(resize) is not int or not 64 <= resize <= 2048):
        raise ValueError("feature_resize must be null or an integer from 64 to 2048")
    checkpoint = optional_path("matcher_checkpoint")
    checksum = data.get("matcher_checkpoint_sha256")
    if checkpoint is not None:
        import re

        if not isinstance(checksum, str) or not re.fullmatch(r"[0-9a-f]{64}", checksum):
            raise ValueError("Adapted matcher requires checkpoint SHA256")
        if not data.get("matcher_full_depth", False):
            raise ValueError("Adapted final head requires full-depth inference")
    elif checksum is not None:
        raise ValueError("Checkpoint checksum without checkpoint")
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
        optional_path("policy_parameters"),
        checkpoint,
        checksum,
        data.get("matcher_full_depth", False),
        resize,
    )


EncoderFactory = Callable[[DetectorConfig, dict], GlobalEncoder]
EngineFactory = Callable[[DetectorConfig, dict], PairEngine]
PolicyFactory = Callable[[DetectorConfig], ProposalPolicy]


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
    family = "aliked" if config.matching == "aliked_lightglue" else "superpoint"
    if family == "aliked":
        for name in ("aliked-n16.pth", "aliked_lightglue_v0-1_arxiv.pth"):
            if f"torch/checkpoints/{name}" not in manifest["artifacts"]:
                raise ValueError("ALIKED weights must be explicitly installed and fingerprinted")
    fingerprint = identity(
        {
            "artifacts": manifest["artifacts"],
            "extractor": family,
            "maximum_keypoints": config.maximum_keypoints,
            "resize": config.feature_resize,
        }
    )
    if family == "aliked":
        from .matching.aliked import AlikedExtractor

        extractor = AlikedExtractor(
            device, config.maximum_keypoints, fingerprint, config.feature_resize
        )
    else:
        extractor = SuperPointExtractor(
            device, config.maximum_keypoints, fingerprint, config.feature_resize
        )
    return SparsePairEngine(
        extractor,
        LightGlueMatcher(
            device,
            family,
            config.match_threshold,
            checkpoint=config.matcher_checkpoint,
            checkpoint_sha256=config.matcher_checkpoint_sha256,
            full_depth=config.matcher_full_depth,
        ),
        fingerprint,
    )


ENCODERS: dict[str, EncoderFactory] = {"megaloc": _megaloc}
ENGINES: dict[str, EngineFactory] = {"superpoint_lightglue": _sparse, "aliked_lightglue": _sparse}


def _confidence(config: DetectorConfig) -> ProposalPolicy:
    import json

    from .policies.confidence import CandidateConfidencePolicy

    if config.policy_parameters is None:
        raise ValueError("Candidate confidence requires policy_parameters")
    parameters = json.loads(config.policy_parameters.read_text())
    if parameters.get("match_threshold") != config.match_threshold:
        raise ValueError("Candidate confidence was fitted for a different match threshold")
    return CandidateConfidencePolicy(parameters)


POLICIES: dict[str, PolicyFactory] = {
    "retrieval_order": lambda config: RetrievalOrderPolicy(),
    "candidate_confidence": _confidence,
}


def build_pair_engine(config: DetectorConfig) -> tuple[PairEngine, dict]:
    """Build the production matching adapter without constructing a retrieval model."""
    import numpy as np
    import torch

    if config.matching not in ENGINES:
        raise ValueError(f"Unregistered LDO matching adapter: {config.matching}")
    install = verify_install(config.model_root)
    if config.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("Configured CUDA device is unavailable")
    torch.hub.set_dir(str(config.model_root / "torch"))
    torch.manual_seed(config.seed)
    np.random.seed(config.seed)
    torch.set_num_threads(1)
    engine = ENGINES[config.matching](config, install)
    return engine, {
        "local_feature_fingerprint": engine.fingerprint,
        "installation": install,
        "matching": config.matching,
        "threshold": config.match_threshold,
        "full_depth": config.matcher_full_depth,
        "checkpoint_sha256": config.matcher_checkpoint_sha256,
        "maximum_keypoints": config.maximum_keypoints,
        "resize": config.feature_resize,
    }


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
            POLICIES[config.policy](config),
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
        "matching_fingerprint": identity(
            {
                "extractor": engine.fingerprint,
                "threshold": config.match_threshold,
                "checkpoint": config.matcher_checkpoint_sha256,
                "full_depth": config.matcher_full_depth,
            }
        ),
        "local_feature_fingerprint": engine.fingerprint,
        "device": config.device,
        "seed": config.seed,
        "match_threshold": config.match_threshold,
        "maximum_keypoints": config.maximum_keypoints,
        "feature_resize": config.feature_resize,
        "matching_adapter": config.matching,
        "matcher_checkpoint_sha256": config.matcher_checkpoint_sha256,
        "matcher_full_depth": config.matcher_full_depth,
        "policy": config.policy,
        "policy_parameters_sha256": sha256(config.policy_parameters)
        if config.policy_parameters
        else None,
        "gpu": torch.cuda.get_device_name(0) if config.device == "cuda" else None,
        "packages": {
            name: importlib.metadata.version(name)
            for name in ("torch", "torchvision", "numpy", "lightglue", "safetensors")
        },
    }
    manifest["manifest_id"] = identity(manifest)
    return detector, manifest
