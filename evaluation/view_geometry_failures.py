"""Build an offline, navigable review of saved TartanAir geometry failures."""

import argparse
import base64
import hashlib
import json
import math
import os
from pathlib import Path

import cv2
import numpy as np

PROJECT = Path(__file__).resolve().parents[1]
TEMPLATE = PROJECT / "src/loop_eval/tasks/feature_matching/viewer/geometry_failures.html"


def local_path(value: str, distro: str) -> Path:
    """Read existing Linux artifacts from Windows without copying the dataset."""
    if os.name == "nt" and value.startswith("/opt/"):
        return Path(f"//wsl.localhost/{distro}{value}")
    return Path(value)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def finite(value):
    if isinstance(value, list):
        return [finite(item) for item in value]
    if isinstance(value, dict):
        return {key: finite(item) for key, item in value.items()}
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def build(results_path: Path, output: Path, distro: str) -> dict:
    raw_results = results_path.read_bytes()
    results = json.loads(raw_results)
    policy = results["policy"]
    images, image_ids, pairs = [], {}, []

    def image_id(filename):
        if filename not in image_ids:
            raw = local_path(filename, distro).read_bytes()
            decoded = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
            if decoded is None:
                raise ValueError(f"Cannot decode saved image: {filename}")
            image_ids[filename] = len(images)
            images.append(
                {
                    "src": "data:image/png;base64," + base64.b64encode(raw).decode(),
                    "width": decoded.shape[1],
                    "height": decoded.shape[0],
                    "sha256": digest(raw),
                    "source": filename,
                }
            )
        return image_ids[filename]

    for event in results["events"]:
        for row in event["pairs"]:
            path = local_path(row["evidence"], distro)
            if digest(path.read_bytes()) != row["evidence_sha256"]:
                raise ValueError(f"Saved evidence changed: {path}")
            with np.load(path, allow_pickle=False) as data:
                failed = np.flatnonzero(data["verdicts"] == "contradicted")
                if not len(failed):
                    continue
                matches = []
                for index in failed:
                    q, h = data["indices"][index]
                    qz, hz = data["query_depth_m"][index], data["historical_depth_m"][index]
                    matches.append(
                        {
                            "original_index": int(index),
                            "query_feature_id": int(q),
                            "historical_feature_id": int(h),
                            "query": data["query_points"][q].tolist(),
                            "historical": data["historical_points"][h].tolist(),
                            "expected_history": data["reference_projected_history_points"][
                                q
                            ].tolist(),
                            "query_depth_m": float(qz),
                            "historical_depth_m": float(hz),
                            "xyz_error_m": float(data["xyz_error_m"][index]),
                            "xyz_gate_m": max(
                                policy["feature_xyz_tolerance_m"],
                                policy["feature_xyz_relative_tolerance"] * max(qz, hz),
                            ),
                            "pixel_error": float(data["pixel_error"][index]),
                        }
                    )
                if len(matches) != row["reported"]["contradicted"]:
                    raise ValueError("Failure count differs from the saved report")
                pairs.append(
                    {
                        "trajectory": row["trajectory"],
                        "event": event["event_id"],
                        "query_ns": row["q"],
                        "history_ns": row["h"],
                        "query_image": image_id(row["query_image"]),
                        "history_image": image_id(row["historical_image"]),
                        "counts": row["reported"],
                        "evidence": row["evidence"],
                        "evidence_sha256": row["evidence_sha256"],
                        "matches": matches,
                    }
                )
    if not pairs:
        raise ValueError("No saved contradicted feature matches to review")
    payload = finite(
        {
            "results_sha256": digest(raw_results),
            "policy": policy,
            "images": images,
            "pairs": pairs,
            "analyzed_pairs": sum(len(event["pairs"]) for event in results["events"]),
        }
    )
    serialized = json.dumps(payload, allow_nan=False, separators=(",", ":"))
    # Prevent paths or metadata from terminating the embedded JSON script block.
    serialized = serialized.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    html = TEMPLATE.read_text(encoding="utf-8").replace("__REVIEW_DATA__", serialized)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
    summary = {
        "output": str(output.resolve()),
        "pairs_with_failures": len(pairs),
        "failed_matches": sum(len(pair["matches"]) for pair in pairs),
        "results_sha256": payload["results_sha256"],
    }
    output.with_suffix(".json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--results",
        type=Path,
        default=PROJECT / "docs/archive/ldo-matching-diagnostics-results.json",
    )
    parser.add_argument(
        "--output", type=Path, default=PROJECT / "evaluation/output/geometry-failures/index.html"
    )
    parser.add_argument("--distro", default="Ubuntu-24.04")
    args = parser.parse_args()
    print(json.dumps(build(args.results, args.output, args.distro), indent=2))


if __name__ == "__main__":
    main()
