"""Pinned public archive installer; hashes and safe extraction are mandatory."""

import hashlib
import json
import shutil
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from loop_eval.tasks.loop_closure.comparison.reference import write_json


def install(settings):
    root = Path(settings["root"])
    root.mkdir(parents=True, exist_ok=True)
    repo, revision = settings["repository"], settings["revision"]
    prefix = f"{settings['environment']}/{settings['difficulty']}"
    api = f"https://huggingface.co/api/datasets/{repo}/tree/{revision}/{prefix}?limit=1000"
    with urllib.request.urlopen(api, timeout=60) as response:
        metadata = {item["path"]: item for item in json.load(response)}
    archive_names = settings.get("archives") or [
        "image_lcam_front.zip",
        "image_rcam_front.zip",
        "depth_lcam_front.zip",
        "depth_rcam_front.zip",
        "imu.zip",
    ]
    allowed = {
        "image_lcam_front.zip",
        "image_rcam_front.zip",
        "depth_lcam_front.zip",
        "depth_rcam_front.zip",
        "imu.zip",
    }
    if not set(archive_names) <= allowed or len(set(archive_names)) != len(archive_names):
        raise ValueError("Invalid requested dataset archives")
    cache = root / "archives"
    cache.mkdir(exist_ok=True)

    def download(name):
        key = prefix + "/" + name
        item = metadata[key]
        expected = item.get("lfs", {}).get("oid")
        if not expected:
            raise ValueError("Official archive metadata lacks SHA256")
        path = cache / name

        def valid():
            if not path.exists() or path.stat().st_size != item["size"]:
                return False
            with path.open("rb") as stream:
                return hashlib.file_digest(stream, "sha256").hexdigest() == expected

        if not valid():
            partial = path.with_suffix(".partial")
            url = f"https://huggingface.co/datasets/{repo}/resolve/{revision}/{key}?download=true"
            print(f"Downloading {name}: {item['size'] / 1e6:.1f} MB", flush=True)
            with urllib.request.urlopen(url, timeout=120) as source, partial.open("wb") as target:
                shutil.copyfileobj(source, target, length=1024 * 1024)
            partial.replace(path)
            if not valid():
                raise ValueError(f"Archive hash mismatch: {name}")
        marker = cache / (name + ".extracted.json")
        if not marker.exists() or json.loads(marker.read_text()).get("archive_sha256") != expected:
            with zipfile.ZipFile(path) as archive:
                for entry in archive.infolist():
                    target = (root / entry.filename).resolve()
                    if not target.is_relative_to(root.resolve()) or entry.filename.startswith("/"):
                        raise ValueError("Unsafe archive path")
                    if entry.is_dir():
                        target.mkdir(parents=True, exist_ok=True)
                    else:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with archive.open(entry) as source, target.open("wb") as destination:
                            shutil.copyfileobj(source, destination, length=1024 * 1024)
            write_json(marker, {"archive_sha256": expected})
        print(f"Verified and extracted {name}", flush=True)
        return {"path": key, "size": item["size"], "sha256": expected}

    with ThreadPoolExecutor(max_workers=2) as pool:
        artifacts = list(pool.map(download, archive_names))
    manifest = {
        "dataset": "TartanAir V2",
        "repository": repo,
        "revision": revision,
        "root": str(root),
        "artifacts": artifacts,
    }
    temporary = root / "installation.pending.json"
    temporary.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    temporary.replace(root / "installation.json")
    return manifest
