"""Read upstream ORB exports; coordinates are mapped to original sensor pixels."""

import hashlib
import json
import struct
from pathlib import Path

import numpy as np

DTYPE = np.dtype(
    [
        ("rectified", "<f4", (2,)),
        ("raw", "<f4", (2,)),
        ("angle", "<f4"),
        ("octave", "<i4"),
        ("descriptor", "u1", (32,)),
    ]
)


def read_features(root, image):
    image = Path(image)
    camera = image.parents[1].name
    path = Path(root) / f"{image.stem}_{camera}.orb"
    data = path.read_bytes()
    manifest = json.loads((Path(root) / "manifest.json").read_text())
    entry = manifest["exports"][path.name]
    if (
        hashlib.sha256(data).hexdigest() != entry["sha256"]
        or hashlib.sha256(image.read_bytes()).hexdigest() != entry["image_sha256"]
    ):
        raise ValueError(f"ORB export or source image differs from manifest: {path}")
    if len(data) < 20 or data[:8] != b"LDORB001":
        raise ValueError(f"Invalid ORB export header: {path}")
    count, width, height = struct.unpack_from("<III", data, 8)
    if len(data) != 20 + count * DTYPE.itemsize or not width or not height:
        raise ValueError(f"Invalid ORB export length/resolution: {path}")
    rows = np.frombuffer(data, DTYPE, count=count, offset=20)
    points = rows["raw"].astype(float)
    if not np.isfinite(points).all():
        raise ValueError(f"Nonfinite ORB coordinates: {path}")
    return points, np.ascontiguousarray(rows["descriptor"]), (width, height)
