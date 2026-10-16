"""Detector-blind reference universe; poses are review aids, never labels."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from loop_eval.tasks.feature_matching.xyz.evaluator import read_replay
from loop_eval.tasks.feature_matching.xyz.poses import CameraPoses


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def prepare(sequence: Path, replay: Path, output: Path, protocol: dict) -> None:
    images = read_replay(replay)
    poses = CameraPoses(sequence, protocol["pose_tolerance_ms"])
    if not poses.available:
        raise ValueError("Reference construction requires ground-truth poses")
    stamps = list(images)
    selected = stamps[:: protocol["query_stride"]]
    output.mkdir(parents=True, exist_ok=False)
    queries, excluded_queries, pair_count = [], [], 0
    with (output / "pairs.jsonl").open("x", encoding="utf-8") as stream:
        for query in selected:
            if poses.get(query) is None:
                excluded_queries.append(query)
                continue
            history = [h for h in stamps if query - h >= protocol["exclusion_ns"]]
            admissible = [h for h in history if poses.get(h) is not None]
            queries.append(
                {
                    "timestamp_ns": query,
                    "eligible_history": len(admissible),
                    "excluded_missing_pose": len(history) - len(admissible),
                }
            )
            for historical in admissible:
                _, aid = poses.relative(query, historical)
                record = {
                    "query_timestamp_ns": query,
                    "historical_timestamp_ns": historical,
                    "query_image": str(images[query]),
                    "historical_image": str(images[historical]),
                    "label": "unknown",
                    "reviewer": "",
                    "reason": "",
                    "pose_review_aid": aid,
                }
                stream.write(json.dumps(record, allow_nan=False) + "\n")
                pair_count += 1
    files = [sequence / "mav0/cam0/sensor.yaml", poses.path, poses.path.parent / "sensor.yaml"]
    manifest = {
        "version": 1,
        "sequence": sequence.name,
        "sequence_path": str(sequence.resolve()),
        "protocol": protocol,
        "replay": str(replay.resolve()),
        "replay_sha256": sha256(replay),
        "images": {str(s): {"path": str(p), "sha256": sha256(p)} for s, p in images.items()},
        "reference_files": {str(p): sha256(p) for p in files},
        "queries": queries,
        "excluded_queries_missing_pose": excluded_queries,
        "pair_count": pair_count,
        "pairs_sha256": sha256(output / "pairs.jsonl"),
        "labels_are_independent": True,
        "rubric": "Enough shared physical scene for useful geometric verification; pose proximity alone is insufficient. Unknown when ambiguous.",
    }
    write_json(output / "manifest.json", manifest)


def load_reference(root: Path) -> tuple[dict, dict[tuple[int, int], dict]]:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("version") != 1 or sha256(root / "pairs.jsonl") != manifest["pairs_sha256"]:
        raise ValueError("Reference universe differs from its manifest")
    records = {}
    with (root / "pairs.jsonl").open(encoding="utf-8") as stream:
        for line in stream:
            item = json.loads(line)
            key = (item["query_timestamp_ns"], item["historical_timestamp_ns"])
            if key in records or item["label"] != "unknown":
                raise ValueError("Invalid base reference record")
            records[key] = item
    if len(records) != manifest["pair_count"]:
        raise ValueError("Reference pair count differs")
    # Append-only review journal; latest explicit review wins, preserving history.
    journal = root / "reviews.jsonl"
    if journal.exists():
        with journal.open(encoding="utf-8") as stream:
            for line in stream:
                review = json.loads(line)
                key = (review["query_timestamp_ns"], review["historical_timestamp_ns"])
                if key not in records or review["label"] not in {"loop", "non_loop", "unknown"}:
                    raise ValueError("Review refers to an invalid pair or label")
                if not review.get("reviewer", "").strip() or not review.get("reason", "").strip():
                    raise ValueError("Every review requires reviewer and justification")
                records[key] = {**records[key], **review}
    return manifest, records


def verify_images(manifest: dict, replay: Path) -> None:
    images = read_replay(replay)
    if set(images) != {int(s) for s in manifest["images"]}:
        raise ValueError("Detector replay timestamps differ from reference")
    for stamp, image in images.items():
        if sha256(image) != manifest["images"][str(stamp)]["sha256"]:
            raise ValueError("Detector replay image contents differ from reference")
