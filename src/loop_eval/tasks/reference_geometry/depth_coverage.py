"""Explain oracle abstentions without changing its frozen numerical decisions."""

import json
from collections import Counter
from pathlib import Path

import numpy as np

from loop_eval.tasks.loop_closure.comparison.reference import sha256

from .geometry import decode_depth, sample_depth

PRIORITY = (
    "outside_image_or_nonfinite_pixel",
    "nonfinite_depth",
    "depth_out_of_range",
    "depth_boundary",
)


def reasons(depth, pixels, policy):
    pixels = np.asarray(pixels, float).reshape(-1, 2)
    xy = np.rint(np.where(np.isfinite(pixels), pixels, -1)).astype(int)
    inside = np.isfinite(pixels).all(axis=1)
    inside &= (
        (xy[:, 0] >= 1)
        & (xy[:, 0] < depth.shape[1] - 1)
        & (xy[:, 1] >= 1)
        & (xy[:, 1] < depth.shape[0] - 1)
    )
    x, y = np.clip(xy[:, 0], 1, depth.shape[1] - 2), np.clip(xy[:, 1], 1, depth.shape[0] - 2)
    values = np.stack([depth[y + dy, x + dx] for dy in (-1, 0, 1) for dx in (-1, 0, 1)])
    z = depth[y, x]
    gates = [
        inside,
        np.isfinite(values).all(axis=0),
        (values.min(axis=0) >= policy["minimum_depth_m"])
        & (values.max(axis=0) <= policy["maximum_depth_m"]),
        values.max(axis=0) - values.min(axis=0)
        <= policy["depth_edge_relative_tolerance"] * np.maximum(z, 1e-12),
    ]
    output = np.full(len(pixels), "usable", dtype="U40")
    for name, gate in reversed(list(zip(PRIORITY, gates, strict=True))):
        output[~gate] = name
    _, valid = sample_depth(depth, pixels, policy)
    if not np.array_equal(output == "usable", valid):
        raise ValueError("Coverage diagnostic disagrees with frozen depth validity")
    return output


def summarize(sequences, artifact_root, policy):
    totals = {
        name: {"untestable": Counter(), "endpoint_reasons": Counter(), "matches": 0}
        for name in ("orb", "ldo")
    }
    for sequence in sequences:
        replay = Path(sequence["reference"]["root"])
        frame_path = replay / "frames.json"
        if sha256(frame_path) != sequence["reference"]["frames_sha256"]:
            raise ValueError("Reference frame metadata changed")
        frames = json.loads(frame_path.read_text())
        depths = {}
        for frame in frames:
            path = Path(frame["depth"])
            if sha256(path) != frame["depth_sha256"]:
                raise ValueError("Reference depth changed")
            depths[frame["timestamp_ns"]] = decode_depth(path)
        evidence = Path(artifact_root) / sequence["trajectory"] / "feature_checks.jsonl"
        if sha256(evidence) != sequence["artifact_hashes"]["feature_checks"]:
            raise ValueError("Feature evidence changed")
        groups = {}
        with evidence.open() as stream:
            for line in stream:
                row = json.loads(line)
                groups.setdefault(
                    (row["method"], row["query_timestamp_ns"], row["historical_timestamp_ns"]), []
                ).append(row)
        for (method, q, h), rows in groups.items():
            qr = reasons(depths[q], [r["query_pixel"] for r in rows], policy)
            hr = reasons(depths[h], [r["historical_pixel"] for r in rows], policy)
            unknown = (qr != "usable") | (hr != "usable")
            if unknown.tolist() != [r["verdict"] == "untestable" for r in rows]:
                raise ValueError("Coverage diagnostic differs from saved feature verdict")
            totals[method]["matches"] += len(rows)
            totals[method]["endpoint_reasons"].update(qr.tolist() + hr.tolist())
            for index in np.flatnonzero(unknown):
                reason = next(r for r in PRIORITY if r in (qr[index], hr[index]))
                totals[method]["untestable"][reason] += 1
    return totals
