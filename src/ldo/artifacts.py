"""Streaming checksums and deterministic experiment identities."""

import hashlib
import json
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def identity(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def verify_install(root: Path) -> dict:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    for filename, expected in manifest["artifacts"].items():
        path = root / filename
        if not path.is_file() or sha256(path) != expected:
            raise ValueError(f"Installed model artifact differs from manifest: {path}")
    return manifest
