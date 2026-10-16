"""Stage selected installed EuRoC archives onto Linux before timed evaluation."""

import argparse
import hashlib
import json
import os
import shutil
import zipfile
from pathlib import Path
from uuid import uuid4


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--sequence", default="MH_01_easy")
    parser.add_argument(
        "--cache-root", type=Path, default=Path("/opt/loop-detector/datasets/euroc")
    )
    args = parser.parse_args()
    if os.name != "posix" or Path(args.sequence).name != args.sequence:
        parser.error("Run inside Linux with a sequence name, not a path")
    source_root, cache_root = args.dataset_root.resolve(), args.cache_root.resolve()
    archive_manifest = json.loads((source_root / "_archives" / f"{args.sequence}.json").read_text())
    identity = {
        "sequence": args.sequence,
        "source_sequence": str(source_root / args.sequence),
        "archive_sha256": archive_manifest["sha256"],
        "validation": "SHA256 and every ZIP entry CRC32",
    }
    destination = cache_root / args.sequence
    if destination.exists():
        if json.loads((destination / "cache_manifest.json").read_text()) != identity:
            raise ValueError("Existing dataset cache does not match source archive")
        print("Verified existing cache:", destination)
        return
    cache_root.mkdir(parents=True, exist_ok=True)
    identifier = uuid4().hex
    archive_path = cache_root / f".{identifier}.zip"
    workspace = cache_root / f".{identifier}.partial"
    workspace.mkdir()
    try:
        checksum = hashlib.sha256()
        print("Copying source archive to Linux:", args.sequence, flush=True)
        with (
            (source_root / "_archives" / f"{args.sequence}.zip").open("rb") as source,
            archive_path.open("xb") as target,
        ):
            while chunk := source.read(4 * 1024 * 1024):
                checksum.update(chunk)
                target.write(chunk)
        if checksum.hexdigest() != archive_manifest["sha256"]:
            raise ValueError("Installed dataset archive SHA256 mismatch")
        print("Extracting and verifying ZIP entries", flush=True)
        with zipfile.ZipFile(archive_path) as archive:
            for name in archive.namelist():
                path = Path(name)
                if (
                    path.is_absolute()
                    or ".." in path.parts
                    or not path.parts
                    or path.parts[0] != "mav0"
                ):
                    raise ValueError(f"Unsafe or unexpected EuRoC ZIP member: {name}")
            archive.extractall(workspace)
        (workspace / "cache_manifest.json").write_text(json.dumps(identity, indent=2))
        workspace.rename(destination)
        print("Dataset cache ready:", destination)
    finally:
        if archive_path.exists():
            archive_path.unlink()
        if workspace.exists():
            workspace.resolve().relative_to(cache_root)
            shutil.rmtree(workspace)


if __name__ == "__main__":
    main()
