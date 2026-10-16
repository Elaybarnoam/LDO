"""Fixed independent image pairs, configured LDO matching, unchanged XYZ."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from collections import defaultdict
from dataclasses import replace
from pathlib import Path

from ldo.artifacts import verify_install
from ldo.configuration import ENGINES, load_config
from ldo.contracts import Candidate, KeyframeInput, LoopProposalBatch
from ldo.evidence import EvidenceWriter
from ldo.memory import FeatureCache
from loop_eval.tasks.feature_matching.xyz.evaluator import check_trace, read_replay
from loop_eval.tasks.feature_matching.xyz.learned_features import SavedCorrespondences

from .reference import load_reference, sha256, verify_images, write_json


def export_orb(
    config: dict, images: dict, selected: list, output: Path, feature_budget: int | None
) -> Path:
    """Isolate stereo caches from historical runs; optionally re-extract at equal cap."""
    import yaml

    root = output / "orb" / "orb_features"
    root.mkdir(parents=True)
    stamps = sorted({stamp for key in selected for stamp in key})
    original = Path(config["matching"]["orb_feature_root"])
    manifest = json.loads((original / "manifest.json").read_text())
    if feature_budget is None:
        exports = {}
        for stamp in stamps:
            for camera in ("cam0", "cam1"):
                name = f"{stamp}_{camera}.orb"
                if sha256(original / name) != manifest["exports"][name]["sha256"]:
                    raise ValueError("Pinned ORB export changed")
                shutil.copyfile(original / name, root / name)
                exports[name] = manifest["exports"][name]
        write_json(root / "manifest.json", {**manifest, "exports": exports})
        return root
    native_config = yaml.safe_load(Path(config["matching"]["orb_config"]).read_text())
    source, build = (Path(native_config["native"][key]) for key in ("source_root", "build_root"))
    build_manifest = json.loads((build / "manifest.json").read_text())
    binary = build / "orb_dbow2"
    if not build_manifest["verification"]["passed"] or build_manifest["verification"][
        "binary_sha256"
    ] != sha256(binary):
        raise ValueError("Native ORB binary is not parity verified")
    for filename, expected in build_manifest["artifacts"].items():
        if sha256(Path(filename)) != expected:
            raise ValueError(f"Pinned native ORB artifact changed: {filename}")
    settings = output / "orb" / "EuRoC.yaml"
    text = (source / "Examples/Stereo-Inertial/EuRoC.yaml").read_text()
    text, replaced = re.subn(
        r"(?m)^(ORBextractor\.nFeatures:\s*)\d+", lambda m: f"{m.group(1)}{feature_budget}", text
    )
    if replaced != 1:
        raise ValueError("Cannot unambiguously set native ORB feature budget")
    settings.write_text(text)
    replay = output / "orb" / "extraction.tsv"
    replay.write_text("".join(f"{stamp}\t{images[stamp]}\n" for stamp in stamps))
    with (
        (output / "orb" / "native.stdout.jsonl").open("x") as stdout,
        (output / "orb" / "native.stderr.log").open("x") as stderr,
    ):
        subprocess.run(
            [
                str(binary),
                str(source / "Vocabulary/ORBvoc.txt"),
                str(settings),
                str(replay),
                str(config["protocol"]["exclusion_ns"]),
                "1",
            ],
            env={**os.environ, "LDO_ORB_FEATURE_DIR": str(root)},
            stdout=stdout,
            stderr=stderr,
            check=True,
            timeout=900,
        )
    exports = {}
    for stamp in stamps:
        for camera in ("cam0", "cam1"):
            image = images[stamp].parents[2] / camera / "data" / images[stamp].name
            name = f"{stamp}_{camera}.orb"
            exports[name] = {"sha256": sha256(root / name), "image_sha256": sha256(image)}
    write_json(
        root / "manifest.json",
        {
            **manifest,
            "exports": exports,
            "feature_budget": feature_budget,
            "settings_sha256": sha256(settings),
            "build_manifest_sha256": sha256(build / "manifest.json"),
        },
    )
    return root


def match_fixed(
    reference_root: Path,
    config: dict,
    output: Path,
    pair_limit: int,
    feature_budget: int | None = None,
) -> dict:
    import numpy as np
    import torch

    manifest, reference = load_reference(reference_root)
    replay = Path(config["methods"]["orb"]["replay"])
    verify_images(manifest, replay)
    images = read_replay(replay)
    # Hash ordering selects pairs independently of images, detectors and verdicts.
    import hashlib

    seed = manifest["protocol"]["seed"]
    keys = sorted(reference, key=lambda key: hashlib.sha256(f"{seed}:{key}".encode()).digest())
    selected = sorted(keys[:pair_limit])
    if not selected:
        raise ValueError("No admissible reference pairs for matching")
    output.mkdir(parents=True, exist_ok=False)
    grouped = defaultdict(list)
    for q, h in selected:
        grouped[q].append(h)
    trace = output / "fixed_pairs.jsonl"
    with trace.open("x", encoding="utf-8") as stream:
        for q in images:
            history = grouped.get(q, [])
            stream.write(
                json.dumps(
                    {
                        "query_timestamp_ns": q,
                        "candidates": [
                            {"rank": i, "historical_timestamp_ns": h, "score": 0.0}
                            for i, h in enumerate(history, 1)
                        ],
                    }
                )
                + "\n"
            )
    detector_path = Path(config["matching"]["ldo_config"])
    detector_config = load_config(detector_path)
    if feature_budget is not None:
        detector_config = replace(detector_config, maximum_keypoints=feature_budget)
    installation = verify_install(detector_config.model_root)
    if detector_config.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("Configured CUDA device unavailable")
    torch.hub.set_dir(str(detector_config.model_root / "torch"))
    torch.manual_seed(seed)
    np.random.seed(seed)
    torch.set_num_threads(1)
    engine = ENGINES[detector_config.matching](detector_config, installation)
    model_manifest = {
        "variant": detector_config.variant,
        "device": detector_config.device,
        "matching_adapter": detector_config.matching,
        "match_threshold": detector_config.match_threshold,
        "matching_fingerprint": engine.fingerprint,
        "effective_seed": seed,
        "installation": installation,
        "detector_config_sha256": sha256(detector_path),
        "experiment": "independently_selected_fixed_pairs",
        "feature_budget": detector_config.maximum_keypoints,
        "pair_selection_seed": seed,
    }
    feature_root = output / "learned_features"
    writer = EvidenceWriter(feature_root, model_manifest)
    cache = FeatureCache(engine, detector_config.cache_size)
    try:
        for q, history in sorted(grouped.items()):
            query = KeyframeInput(str(q), q, images[q], manifest["sequence"])
            qfeatures = cache.get(images[q])
            candidates = []
            for rank, h in enumerate(history, 1):
                hfeatures = cache.get(images[h])
                candidates.append(
                    Candidate(
                        KeyframeInput(str(h), h, images[h], manifest["sequence"]),
                        rank,
                        0.0,
                        engine.match(qfeatures, hfeatures),
                        hfeatures,
                    )
                )
            writer.append(LoopProposalBatch(query, qfeatures, tuple(candidates), len(history)))
        writer.finalize()
    finally:
        cache.clear()
        engine.close()
    if detector_config.device == "cuda":
        torch.cuda.empty_cache()
    sequence = Path(manifest["sequence_path"])
    policy = Path(config["matching"]["xyz_config"])
    orb_root = export_orb(config, images, selected, output, feature_budget)
    # Both adapters now use output/stereo_correspondences: the same calibrated
    # dense predictions for these fixed pairs, independent of model assignments.
    # ORB's root is nested one level; place LDO exports at the same parent.
    orb_cache = orb_root.parent / "stereo_correspondences"
    shared_cache = feature_root.parent / "stereo_correspondences"
    orb_cache.symlink_to(shared_cache, target_is_directory=True)
    shared_cache.mkdir(exist_ok=True)
    for name in ("orb", "ldo"):
        check_trace(
            sequence,
            replay,
            trace,
            output / name / "candidate_checks",
            policy,
            feature_root=orb_root if name == "orb" else feature_root,
            correspondence_source=SavedCorrespondences(feature_root) if name == "ldo" else None,
            on_log=print,
        )
    result = {
        "pairs": len(selected),
        "selection": "seeded hash sample of independent reference universe",
        "reference_manifest_sha256": sha256(reference_root / "manifest.json"),
        "trace_sha256": sha256(trace),
        "xyz_policy_sha256": sha256(policy),
        "orb_feature_manifest_sha256": sha256(orb_root / "manifest.json"),
        "model_manifest": model_manifest,
        "budget_mode": "equal_requested_extraction_cap"
        if feature_budget is not None
        else "normal_configurations",
        "requested_feature_budget": feature_budget,
        "checks": {name: str(output / name / "candidate_checks") for name in ("orb", "ldo")},
    }
    write_json(output / "manifest.json", result)
    return result
