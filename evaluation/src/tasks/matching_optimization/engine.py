"""Run production matchers on frozen pairs, with independent reference assessment."""

import json
from dataclasses import asdict, replace
from pathlib import Path
from time import perf_counter

import cv2
import numpy as np

from ldo.artifacts import identity, sha256, write_json
from ldo.configuration import build_pair_engine
from ldo.contracts import LocalFeatures
from tasks.reference_depth_v2.geometry import check_features
from tasks.reference_geometry.detectors import FeaturePairs
from tasks.reference_geometry.direct import load_sequence
from tasks.reference_geometry.geometry import decode_depth

KEYS = ("supported", "contradicted", "untestable")


def variant_config(base, variant):
    return replace(
        base,
        match_threshold=variant["threshold"],
        matcher_full_depth=variant["full_depth"],
        maximum_keypoints=variant["keypoints"],
        feature_resize=variant["resize"],
        matching=f"{variant['family']}_lightglue",
    )


def references(context, assets):
    frames, _, _ = load_sequence(context["reference"])
    asset = next(a for a in assets["environments"] if a["environment"] == context["environment"])
    labels_path = Path(asset["root"]) / "seg_label_map.json"
    if sha256(labels_path) != asset["labels_sha256"]:
        raise ValueError("Reference semantic labels changed")
    labels = json.loads(labels_path.read_text())["name_map"]
    selected = {r[key] for r in context["pairs"] for key in ("q", "h")}
    items, depth, masks, poses, hashes = {}, {}, {}, {}, {}
    for frame in frames:
        stamp = frame["timestamp_ns"]
        if stamp not in selected:
            continue
        items[stamp] = frame
        depth[stamp] = decode_depth(frame["depth"])
        poses[stamp] = np.asarray(frame["pose"])
        path = (
            Path(asset["root"])
            / asset["environment"]
            / Path(*Path(frame["depth"]).parts[-4:-2])
            / "seg_lcam_front"
            / f"{frame['source_index']:06d}_lcam_front_seg.png"
        )
        masks[stamp] = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
        if masks[stamp] is None or masks[stamp].shape != depth[stamp].shape:
            raise ValueError("Missing aligned reference semantics")
        hashes[str(path)] = sha256(path)
    if selected != set(items):
        raise ValueError("Fixed pair timestamps lack reference frames")
    return items, depth, masks, poses, labels, hashes


class FeatureStore:
    def __init__(self, root, engine, items):
        self.root, self.engine, self.items = root, engine, items
        root.mkdir(parents=True, exist_ok=True)
        self.cache, self.hashes = {}, {}
        marker = root / "manifest.json"
        self.previous = json.loads(marker.read_text()) if marker.exists() else {}

    def get(self, stamp):
        if stamp in self.cache:
            return self.cache[stamp]
        image = Path(self.items[stamp]["image"])
        path = self.root / f"{stamp}.npz"
        if path.exists() and str(stamp) in self.previous:
            old = self.previous[str(stamp)]
            if (
                sha256(path) != old["sha256"]
                or self.items[stamp]["image_sha256"] != old["image_sha256"]
            ):
                raise ValueError("Cached extractor evidence changed")
            with np.load(path, allow_pickle=False) as saved:
                features = LocalFeatures(
                    saved["points"],
                    saved["descriptors"],
                    saved["scores"],
                    tuple(saved["image_size"].tolist()),
                    str(saved["family"]),
                    self.engine.fingerprint,
                )
        else:
            features = self.engine.extract(image)
            np.savez(
                path,
                points=features.points,
                descriptors=features.descriptors,
                scores=features.scores,
                image_size=features.image_size,
                family=features.family,
            )
        self.hashes[str(stamp)] = {
            "sha256": sha256(path),
            "image_sha256": self.items[stamp]["image_sha256"],
        }
        self.cache[stamp] = features
        return features

    def finish(self):
        write_json(self.root / "manifest.json", {**self.previous, **self.hashes})


def evaluate_context(context, engine, variant, assets, policy, output, feature_root, orb=False):
    items, depths, masks, poses, labels, hashes = references(context, assets)
    scene_dir = output / context["environment"] / context["trajectory"]
    scene_dir.mkdir(parents=True, exist_ok=True)
    if orb:
        features = FeaturePairs(
            Path(context["orb_root"]), "orb", {s: Path(f["image"]) for s, f in items.items()}
        )
    else:
        features = FeatureStore(
            feature_root / engine.fingerprint / context["environment"] / context["trajectory"],
            engine,
            items,
        )
    rows = []
    for pair in context["pairs"]:
        q, h = pair["q"], pair["h"]
        started = perf_counter()
        if orb:
            qpoints, _ = features.features(q)
            hpoints, _ = features.features(h)
            ids = features.assignments(q, h)
            scores = np.zeros(len(ids), np.float32)
        else:
            qfeatures, hfeatures = features.get(q), features.get(h)
            assignments = engine.match(qfeatures, hfeatures)
            qpoints, hpoints = qfeatures.points, hfeatures.points
            ids, scores = assignments.indices, assignments.scores
        elapsed = (perf_counter() - started) * 1000
        assessed = check_features(
            qpoints[ids[:, 0]],
            hpoints[ids[:, 1]],
            depths[q],
            depths[h],
            masks[q],
            masks[h],
            np.linalg.inv(poses[h]) @ poses[q],
            set(labels.values()),
            labels["sky"],
            policy,
        )
        path = scene_dir / f"{q}_{h}.npz"
        np.savez_compressed(
            path,
            indices=ids,
            scores=scores,
            query_points=qpoints[ids[:, 0]],
            historical_points=hpoints[ids[:, 1]],
            **assessed,
        )
        counts = {key: int(np.sum(assessed["verdicts"] == key)) for key in KEYS}
        rows.append(
            {
                **pair,
                "environment": context["environment"],
                "trajectory": context["trajectory"],
                "split": context["split"],
                "counts": counts,
                "matching_ms": elapsed,
                "evidence": str(path),
                "sha256": sha256(path),
            }
        )
    if not orb:
        features.finish()
    return rows, hashes


def run_variant(contexts, base, variant, assets, policy, root, orb=False):
    key = "orb" if orb else identity(variant)[:16]
    output = root / "variants" / key
    marker = output / "summary.json"
    context_hash = identity(contexts)
    if marker.exists():
        result = json.loads(marker.read_text())
        if result["contexts_sha256"] != context_hash or result["variant"] != variant:
            raise ValueError("Variant resume inputs changed")
        for row in result["rows"]:
            if sha256(Path(row["evidence"])) != row["sha256"]:
                raise ValueError("Saved matcher output changed")
        return result
    output.mkdir(parents=True, exist_ok=True)
    engine, manifest = (None, {}) if orb else build_pair_engine(variant_config(base, variant))
    rows, semantic_hashes = [], {}
    try:
        for context in contexts:
            current, hashes = evaluate_context(
                context, engine, variant, assets, policy, output, root / "features", orb
            )
            rows.extend(current)
            semantic_hashes.update(hashes)
            print(
                f"Matched {key}: {context['environment']}/{context['trajectory']} ({len(current)} pairs)",
                flush=True,
            )
    finally:
        if engine is not None:
            engine.close()
    result = {
        "id": key,
        "variant": variant,
        "rows": rows,
        "manifest": manifest,
        "contexts_sha256": context_hash,
        "semantic_sha256": semantic_hashes,
        "base_configuration": {
            k: str(v) if isinstance(v, Path) else v for k, v in asdict(base).items()
        },
    }
    write_json(marker, result)
    return result


def threshold_variant(original, threshold, root):
    variant = {**original["variant"], "threshold": threshold}
    key = identity(variant)[:16]
    output = root / "variants" / key
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for old in original["rows"]:
        if sha256(Path(old["evidence"])) != old["sha256"]:
            raise ValueError("Confidence sweep evidence changed")
        with np.load(old["evidence"], allow_pickle=False) as saved:
            mask = saved["scores"] > np.float32(threshold)
            values = {name: saved[name][mask] for name in saved.files}
        path = output / old["environment"] / old["trajectory"] / Path(old["evidence"]).name
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, **values)
        rows.append(
            {
                **old,
                "counts": {k: int(np.sum(values["verdicts"] == k)) for k in KEYS},
                "evidence": str(path),
                "sha256": sha256(path),
            }
        )
    result = {
        **original,
        "id": key,
        "variant": variant,
        "rows": rows,
        "postfiltered_from": original["id"],
    }
    write_json(output / "summary.json", result)
    return result
