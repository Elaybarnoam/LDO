"""Rescore saved feature evidence; no detector, matcher or pose fitting is invoked."""

import argparse
import gzip
import json
import shutil
from collections import Counter
from datetime import UTC, datetime
from itertools import groupby
from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np
import yaml

from tasks.loop_closure.comparison.cli import publish_report
from tasks.loop_closure.comparison.reference import sha256, write_json
from tasks.reference_geometry.direct import load_sequence
from tasks.reference_geometry.geometry import decode_depth

from .assets import install
from .geometry import check_features

ROOT = Path(__file__).resolve().parents[4]
CONFIG = Path(__file__).with_name("config.yaml")
KEYS = ("supported", "contradicted", "untestable")
REASONS = (
    "outside_image_or_nonfinite_pixel",
    "nonpositive_or_nonfinite_depth",
    "sky",
    "unmapped_semantics",
    "ambiguous_depth_boundary",
)


def blank():
    return {
        "old": Counter(dict.fromkeys(KEYS, 0)),
        "new": Counter(dict.fromkeys(KEYS, 0)),
        "transitions": Counter(),
        "unknown_reasons": Counter(),
        "distance_bins": {
            k: Counter(dict.fromkeys(KEYS, 0))
            for k in ("0_to_50_m", "50_to_200_m", "over_200_m", "unknown_depth")
        },
    }


def merge(target, source):
    for key in ("old", "new", "transitions", "unknown_reasons"):
        target[key].update(source[key])
    for key, counts in source["distance_bins"].items():
        target["distance_bins"][key].update(counts)


def rescore_sequence(sequence, asset, policy, output):
    items, _, _ = load_sequence(sequence["reference"])
    labels_path = Path(asset["root"]) / "seg_label_map.json"
    if sha256(labels_path) != asset["labels_sha256"]:
        raise ValueError("Semantic mapping changed")
    labels = json.loads(labels_path.read_text())["name_map"]
    known, sky = set(labels.values()), labels["sky"]
    depths, masks, poses, mask_hashes = {}, {}, {}, {}
    for frame in items:
        stamp = frame["timestamp_ns"]
        depths[stamp] = decode_depth(frame["depth"])
        poses[stamp] = np.asarray(frame["pose"])
        relative_path = Path(frame["depth"]).parts[-4:-2]
        # Source index is frozen in replay metadata, not inferred from timestamps.
        path = (
            Path(asset["root"])
            / asset["environment"]
            / Path(*relative_path)
            / "seg_lcam_front"
            / f"{frame['source_index']:06d}_lcam_front_seg.png"
        )
        mask = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
        if mask is None or mask.shape != depths[stamp].shape or mask.dtype != np.uint8:
            raise ValueError(f"Missing or malformed semantic reference: {path}")
        masks[stamp], mask_hashes[str(path)] = mask, sha256(path)
    source = (
        Path(sequence["feature_evidence_root"]) / sequence["trajectory"] / "feature_checks.jsonl"
    )
    if sha256(source) != sequence["artifact_hashes"]["feature_checks"]:
        raise ValueError("Saved original feature assignments changed")
    stats = {name: blank() for name in ("orb", "ldo")}
    destination = output / f"{sequence['trajectory']}.jsonl.gz"
    with source.open() as stream, gzip.open(destination, "wt", encoding="utf-8") as target:
        rows = (json.loads(line) for line in stream)
        for (method, q, h), group in groupby(
            rows, key=lambda r: (r["method"], r["query_timestamp_ns"], r["historical_timestamp_ns"])
        ):
            pair = list(group)
            result = check_features(
                [r["query_pixel"] for r in pair],
                [r["historical_pixel"] for r in pair],
                depths[q],
                depths[h],
                masks[q],
                masks[h],
                np.linalg.inv(poses[h]) @ poses[q],
                known,
                sky,
                policy,
            )
            current = stats[method]
            for i, row in enumerate(pair):
                old, new = row["verdict"], str(result["verdicts"][i])
                if old not in KEYS:
                    raise ValueError("Unexpected original verdict")
                qr, hr = str(result["query_reason"][i]), str(result["historical_reason"][i])
                current["old"][old] += 1
                current["new"][new] += 1
                current["transitions"][f"{old}->{new}"] += 1
                if new == "untestable":
                    current["unknown_reasons"][next(r for r in REASONS if r in (qr, hr))] += 1
                zq, zh = result["query_depth_m"][i], result["historical_depth_m"][i]
                distance = max(zq, zh) if np.isfinite([zq, zh]).all() else None
                bucket = (
                    "unknown_depth"
                    if distance is None
                    else "0_to_50_m"
                    if distance <= 50
                    else "50_to_200_m"
                    if distance <= 200
                    else "over_200_m"
                )
                current["distance_bins"][bucket][new] += 1
                evidence = {
                    key: row[key]
                    for key in (
                        "method",
                        "query_timestamp_ns",
                        "historical_timestamp_ns",
                        "query_feature_id",
                        "historical_feature_id",
                        "query_pixel",
                        "historical_pixel",
                    )
                }
                evidence.update(
                    {
                        "old_verdict": old,
                        "verdict": new,
                        "query_reason": qr,
                        "historical_reason": hr,
                    }
                )
                for key in ("query_depth_m", "historical_depth_m", "xyz_error_m", "pixel_error"):
                    value = result[key][i]
                    evidence[key] = float(value) if np.isfinite(value) else None
                target.write(json.dumps(evidence, allow_nan=False) + "\n")
    for method, counts in stats.items():
        expected = {key: sequence["features"][method][key] for key in KEYS}
        if dict(counts["old"]) != expected:
            raise ValueError("Replay counts differ from original evidence")
    result = {
        "trajectory": sequence["trajectory"],
        "methods": stats,
        "source_evidence_sha256": sha256(source),
        "evidence": str(destination),
        "evidence_sha256": sha256(destination),
        "semantic_mask_sha256": mask_hashes,
        "frames_sha256": sequence["reference"]["frames_sha256"],
    }
    write_json(output / f"{sequence['trajectory']}.json", result)
    print(
        f"Rescored {asset['environment']}/{sequence['trajectory']}: " + json.dumps(stats),
        flush=True,
    )
    return result


def run(config_path=CONFIG):
    settings = yaml.safe_load(config_path.read_text())
    if settings["version"] != 2:
        raise ValueError("Require reference evaluator version 2")
    source_path = ROOT / settings["source"]
    source = json.loads(source_path.read_text())
    asset_root = Path(settings["asset_root"])
    marker = asset_root / "installation.json"
    assets = json.loads(marker.read_text()) if marker.exists() else install(source, asset_root)
    output = Path(settings["artifact_root"]) / f"rescore_{uuid4().hex}"
    output.mkdir(parents=True, exist_ok=False)
    snapshot = output / "source"
    snapshot.mkdir()
    for path in Path(__file__).parent.glob("*.py"):
        shutil.copyfile(path, snapshot / path.name)
    shutil.copyfile(config_path, output / "config.yaml")
    result = {
        "version": 2,
        "created_at": datetime.now(UTC).isoformat(),
        "source_results_sha256": sha256(source_path),
        "source_results": str(source_path),
        "configuration": settings,
        "configuration_sha256": sha256(config_path),
        "source_sha256": {p.name: sha256(p) for p in snapshot.glob("*.py")},
        "original_geometry_sha256": sha256(
            ROOT / "evaluation/src/tasks/reference_geometry/geometry.py"
        ),
        "assets": assets,
        "detectors_rerun": False,
        "candidate_labels_changed": False,
        "environments": [],
        "aggregate": {m: blank() for m in ("orb", "ldo")},
    }
    for environment in source["environments"]:
        name = environment["environment"]
        if sha256(Path(environment["report"])) != environment["report_sha256"]:
            raise ValueError("Original dated report changed")
        asset = next(a for a in assets["environments"] if a["environment"] == name)
        if sha256(Path(asset["root"]) / "seg_lcam_front.zip") != asset["archive_sha256"]:
            raise ValueError("Semantic reference archive changed")
        directory = output / name
        directory.mkdir()
        scene = {
            "environment": name,
            "methods": {m: blank() for m in ("orb", "ldo")},
            "sequences": [],
        }
        for sequence in environment["task"]["sequences"]:
            sequence = {
                **sequence,
                "feature_evidence_root": environment["task"]["artifact_directory"],
            }
            scored = rescore_sequence(sequence, asset, settings, directory)
            scene["sequences"].append(scored)
            for method, counts in scored["methods"].items():
                merge(scene["methods"][method], counts)
                merge(result["aggregate"][method], counts)
        result["environments"].append(scene)
    write_json(output / "summary.json", result)
    from .report import render  # Ensure source snapshot includes the renderer before publishing.

    if not render(result):
        raise ValueError("Empty evaluation report")
    report = publish_report(
        {"sequence": "TartanAir depth evaluator v2", "reference_depth_v2": result},
        ROOT / "evaluation/output",
        config_path,
    )
    published_source = report.with_suffix("") / "source/reference_depth_v2"
    shutil.copytree(snapshot, published_source)
    write_json(
        ROOT / "evaluation/output/reference_depth_v2.json",
        {
            "report": str(report),
            "report_sha256": sha256(report),
            "summary": str(output / "summary.json"),
            "summary_sha256": sha256(output / "summary.json"),
        },
    )
    print(report, flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=CONFIG)
    args = parser.parse_args()
    run(args.config)


if __name__ == "__main__":
    main()
