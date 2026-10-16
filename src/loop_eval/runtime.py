"""Materialize a local runtime profile without changing published configurations."""

import argparse
import os
from pathlib import Path

import yaml

from .paths import project_root


def materialize(output: Path, runtime_root: str) -> int:
    """Create new profiles, preserving numerical values and existing files."""
    source = project_root() / "configs"
    if not source.is_dir():
        raise ValueError("Runtime profiles must be generated from a source checkout")
    if not runtime_root.startswith("/") or runtime_root == "/":
        raise ValueError("runtime-root must be an absolute Linux runtime directory")
    output = output.expanduser().resolve()
    if output.exists():
        raise FileExistsError(f"Choose a new profile directory: {output}")
    paths = sorted(source.rglob("*.yaml"))

    def replace(value):
        if isinstance(value, dict):
            return {key: replace(item) for key, item in value.items()}
        if isinstance(value, list):
            return [replace(item) for item in value]
        if isinstance(value, str):
            if value.startswith("/opt/loop-detector/"):
                return runtime_root.rstrip("/") + value[len("/opt/loop-detector") :]
            if value.startswith("configs/"):
                return str(output / value.removeprefix("configs/"))
        return value

    for path in paths:
        target = output / path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            yaml.safe_dump(
                replace(yaml.safe_load(path.read_text(encoding="utf-8"))), sort_keys=False
            ),
            encoding="utf-8",
        )
    # Frozen policy parameters must travel with the recipes that reference them.
    for path in source.rglob("*.json"):
        target = output / path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
    return len(paths)


def main(arguments=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--runtime-root", required=True, help="Linux path, e.g. /home/you/ldo-runtime"
    )
    args = parser.parse_args(arguments)
    count = materialize(args.output, args.runtime_root)
    print(f"Wrote {count} configurations to {args.output.resolve()}")
    print(f"Set LDO_CONFIG_ROOT={args.output.resolve()} in the experiment process.")
    if os.name == "nt":
        print(
            "Generate profiles inside WSL for Linux experiments so inter-recipe paths are Linux paths."
        )
