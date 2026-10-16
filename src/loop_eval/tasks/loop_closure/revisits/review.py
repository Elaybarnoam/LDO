"""Blind review of original observations with neighboring-frame context."""

import json
import os
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

import cv2
import numpy as np

from ..comparison.reference import load_reference, sha256
from .reference import append_review


def native_image_path(value: str) -> Path:
    if os.name != "nt" or not value.startswith("/"):
        return Path(value)
    parts = PurePosixPath(value).parts
    if len(parts) > 3 and parts[1] == "mnt" and len(parts[2]) == 1:
        return Path(parts[2].upper() + ":/").joinpath(*parts[3:])
    return Path(r"\\wsl.localhost\Ubuntu-24.04").joinpath(*parts[1:])


def review(root: Path, reviewer: str) -> None:
    if not reviewer.strip():
        raise ValueError("Reviewer identity required")
    manifest, records = load_reference(root)
    proposals = [json.loads(line) for line in (root / "proposals.jsonl").read_text().splitlines()]
    prioritized = list(dict.fromkeys(tuple(pair) for p in proposals for pair in p["pairs"]))
    proposed_set = set(prioritized)
    all_pairs = prioritized + [pair for pair in records if pair not in proposed_set]
    pair_indices = {pair: i for i, pair in enumerate(all_pairs)}
    if not all_pairs:
        raise ValueError("No pose-admitted reference pairs")
    stamps = sorted(map(int, manifest["images"]))
    positions = {q: i for i, q in enumerate(stamps)}
    checked = set()
    title = "LDO independent revisit reference (detector blind)"
    index = 0

    def image(stamp):
        item = manifest["images"][str(stamp)]
        path = native_image_path(item["path"])
        if stamp not in checked:
            if sha256(path) != item["sha256"]:
                raise ValueError("Original reference image changed")
            checked.add(stamp)
        result = cv2.imread(str(path))
        if result is None:
            raise ValueError(f"Cannot load original image {path}")
        return cv2.resize(result, (376, 240))

    try:
        while True:
            q, h = all_pairs[index]
            strips = []
            for stamp in (q, h):
                i = positions[stamp]
                context = [stamps[max(0, min(len(stamps) - 1, i + delta))] for delta in (-2, 0, 2)]
                strips.append(np.hstack([image(s) for s in context]))
            banner = np.zeros((140, strips[0].shape[1], 3), dtype=np.uint8)
            text = [
                f"Blind review {index + 1}/{len(all_pairs)} | reviewer: {reviewer}",
                f"Query row: {q} | History row: {h} | center images are the reviewed pair",
                "L/N/U label | A/D pairs | W/S query | J/K history | G timestamp jump | Q quit",
                "Decisions require reason. Optional interval bounds entered in terminal.",
            ]
            for i, line in enumerate(text):
                cv2.putText(
                    banner,
                    line,
                    (12, 26 + 32 * i),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (235, 235, 235),
                    1,
                    cv2.LINE_AA,
                )
            cv2.imshow(title, np.vstack([banner, *strips]))
            key = cv2.waitKey(100) & 0xFF
            if key == ord("q") or cv2.getWindowProperty(title, cv2.WND_PROP_VISIBLE) < 1:
                break
            if key == ord("a"):
                index = max(0, index - 1)
            elif key == ord("d"):
                index = min(len(all_pairs) - 1, index + 1)
            elif key == ord("g"):
                raw = input("Query and history timestamps to inspect: ").split()
                try:
                    pair = tuple(int(x) for x in raw)
                except ValueError:
                    print("Two integer timestamps required")
                    continue
                if pair not in pair_indices:
                    print("Pair is outside the admitted reference universe")
                else:
                    index = pair_indices[pair]
            elif key in (ord("w"), ord("s"), ord("j"), ord("k")):
                side = 0 if key in (ord("w"), ord("s")) else 1
                direction = -1 if key in (ord("w"), ord("j")) else 1
                candidate = [q, h]
                position = positions[candidate[side]] + direction
                while 0 <= position < len(stamps):
                    candidate[side] = stamps[position]
                    if tuple(candidate) in pair_indices:
                        index = pair_indices[tuple(candidate)]
                        break
                    position += direction
            elif key in (ord("l"), ord("n"), ord("u")):
                label = {ord("l"): "loop", ord("n"): "non_loop", ord("u"): "unknown"}[key]
                raw = input("Optional q_start q_end h_start h_end (blank = center pair): ").strip()
                bounds = [int(x) for x in raw.split()] if raw else [q, q, h, h]
                if len(bounds) != 4:
                    print("Four replay timestamps required; decision cancelled")
                    continue
                reason = input(
                    f"Reason for {label}; confirm judgment covers entire rectangle (blank cancels): "
                ).strip()
                if not reason:
                    continue
                hard_negative = (
                    label == "non_loop"
                    and input("Similar repeated scene / hard negative? [y/N]: ").strip().lower()
                    == "y"
                )
                decision = dict(
                    zip(
                        (
                            "query_start_ns",
                            "query_end_ns",
                            "historical_start_ns",
                            "historical_end_ns",
                        ),
                        bounds,
                        strict=True,
                    )
                )
                decision.update(
                    label=label,
                    reviewer=reviewer.strip(),
                    reason=reason,
                    reviewed_at=datetime.now(UTC).isoformat(),
                    detector_blind=True,
                    hard_negative=hard_negative,
                )
                try:
                    append_review(root, decision)
                except ValueError as error:
                    print(f"Review not saved: {error}")
                    continue
                index = min(len(all_pairs) - 1, index + 1)
    finally:
        cv2.destroyAllWindows()
