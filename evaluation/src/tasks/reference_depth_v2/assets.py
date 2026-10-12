"""Install pinned semantic reference masks without altering old dataset manifests."""

import json
import shutil
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor

from ldo.artifacts import sha256, write_json

REPOSITORY = "theairlabcmu/tartanair2"
REVISION = "0d2d145e973832742a2aaa04b7d2ebffc8d82817"
MAP_REVISION = "158a6844d782942110967325ca3082f50ab2bfc7"


def surface_labels(labels):
    """Uninterpretable classes remain unknown; some scenes have no named sky."""
    names = labels["name_map"]
    filtered = {
        name: value
        for name, value in names.items()
        if name.lower() not in {"z", "unknown", "unlabeled", "void"}
    }
    filtered.setdefault("sky", -1)  # No uint8 pixel can equal the absent-class sentinel.
    return {**labels, "name_map": filtered}


def fetch(url, path, expected=None):
    if not path.exists() or (expected and sha256(path) != expected):
        pending = path.with_suffix(".partial")
        with urllib.request.urlopen(url, timeout=120) as source, pending.open("wb") as target:
            shutil.copyfileobj(source, target, length=1024 * 1024)
        if expected and sha256(pending) != expected:
            raise ValueError("Semantic asset SHA256 mismatch")
        pending.replace(path)
    return sha256(path)


def install(source_result, root):
    root.mkdir(parents=True, exist_ok=True)
    maps = root / "segfiles.zip"
    map_hash = fetch(
        f"https://raw.githubusercontent.com/castacks/tartanairpy/{MAP_REVISION}/segfiles.zip",
        maps,
    )

    def one(item):
        environment = item["environment"]
        dataset = item["task"]["manifest"]["dataset"]
        if dataset["revision"] != REVISION or dataset["repository"] != REPOSITORY:
            raise ValueError("Unexpected dataset revision")
        prefix = f"{environment}/{dataset['difficulty']}"
        with urllib.request.urlopen(
            f"https://huggingface.co/api/datasets/{REPOSITORY}/tree/{REVISION}/{prefix}?limit=1000",
            timeout=60,
        ) as response:
            metadata = json.load(response)
        key = prefix + "/seg_lcam_front.zip"
        entry = next(e for e in metadata if e["path"] == key)
        expected = entry["lfs"]["oid"]
        directory = root / environment
        directory.mkdir(exist_ok=True)
        archive_path = directory / "seg_lcam_front.zip"
        archive_hash = fetch(
            f"https://huggingface.co/datasets/{REPOSITORY}/resolve/{REVISION}/{key}?download=true",
            archive_path,
            expected,
        )
        if archive_path.stat().st_size != entry["size"]:
            raise ValueError("Semantic archive size differs")
        with zipfile.ZipFile(archive_path) as archive:
            for member in archive.infolist():
                target = (directory / member.filename).resolve()
                if not target.is_relative_to(directory.resolve()):
                    raise ValueError("Unsafe semantic archive member")
            archive.extractall(directory)
        with zipfile.ZipFile(maps) as archive:
            labels = surface_labels(json.loads(archive.read(f"{environment}/seg_label_map.json")))
        write_json(directory / "seg_label_map.json", labels)
        print(f"Verified semantic references: {environment}", flush=True)
        return {
            "environment": environment,
            "root": str(directory),
            "archive_sha256": archive_hash,
            "archive_bytes": entry["size"],
            "labels_sha256": sha256(directory / "seg_label_map.json"),
            "sky_label": labels["name_map"]["sky"],
        }

    with ThreadPoolExecutor(max_workers=2) as pool:
        items = list(pool.map(one, source_result["environments"]))
    manifest = {
        "repository": REPOSITORY,
        "revision": REVISION,
        "map_revision": MAP_REVISION,
        "map_archive_sha256": map_hash,
        "environments": items,
    }
    write_json(root / "installation.json", manifest)
    return manifest
