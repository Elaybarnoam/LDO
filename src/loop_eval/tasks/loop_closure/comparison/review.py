"""Detector-blind OpenCV reference review with append-only decisions."""

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import cv2
import numpy as np

from .reference import load_reference, sha256


def review(root: Path, reviewer: str) -> None:
    if not reviewer.strip():
        raise ValueError("Reviewer identity is required")
    manifest, records = load_reference(root)
    items = list(records.values())
    if not items:
        raise ValueError("Reference has no admissible pairs")
    index = next((i for i, item in enumerate(items) if item["label"] == "unknown"), 0)
    checked_images = set()
    title = "LDO independent reference review"
    try:
        while True:
            item = items[index]
            images = []
            for side in ("query", "historical"):
                stamp = str(item[f"{side}_timestamp_ns"])
                path = Path(manifest["images"][stamp]["path"])
                if os.name == "nt" and str(path).startswith("\\opt\\"):
                    path = Path("\\\\wsl.localhost\\Ubuntu-24.04" + str(path))
                if stamp not in checked_images:
                    if sha256(path) != manifest["images"][stamp]["sha256"]:
                        raise ValueError("Reference image changed")
                    checked_images.add(stamp)
                image = cv2.imread(str(path))
                if image is None:
                    raise ValueError(f"Cannot load {path}")
                images.append(image)
            panel = np.hstack(images)
            banner = np.zeros((140, panel.shape[1], 3), dtype=np.uint8)
            lines = [
                f"Independent reference {index + 1}/{len(items)} | {item['label']}",
                "L: loop   N: non-loop   U: unknown   A/D: previous/next   Q: quit",
                "Judge shared physical scene. Pose proximity and detector outputs are not labels.",
                f"Current (left): {item['query_timestamp_ns']} | History (right): {item['historical_timestamp_ns']}",
            ]
            for row, text in enumerate(lines):
                cv2.putText(
                    banner,
                    text,
                    (15, 27 + row * 32),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (235, 235, 235),
                    1,
                    cv2.LINE_AA,
                )
            cv2.imshow(title, np.vstack([banner, panel]))
            key = cv2.waitKey(100) & 0xFF
            if key == ord("q") or cv2.getWindowProperty(title, cv2.WND_PROP_VISIBLE) < 1:
                break
            if key == ord("a"):
                index = max(0, index - 1)
            elif key == ord("d"):
                index = min(len(items) - 1, index + 1)
            elif key in (ord("l"), ord("n"), ord("u")):
                label = {ord("l"): "loop", ord("n"): "non_loop", ord("u"): "unknown"}[key]
                reason = input(f"Justification for {label} (empty cancels): ").strip()
                if not reason:
                    continue
                decision = {
                    "query_timestamp_ns": item["query_timestamp_ns"],
                    "historical_timestamp_ns": item["historical_timestamp_ns"],
                    "label": label,
                    "reviewer": reviewer,
                    "reason": reason,
                    "reviewed_at": datetime.now(UTC).isoformat(),
                }
                with (root / "reviews.jsonl").open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(decision, allow_nan=False) + "\n")
                items[index] = {**item, **decision}
                index = min(len(items) - 1, index + 1)
    finally:
        cv2.destroyAllWindows()
