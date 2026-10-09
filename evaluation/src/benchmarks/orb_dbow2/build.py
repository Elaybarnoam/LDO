"""Build a retrieval-only binary against the already installed pinned source."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path("/opt/loop-detector/ORB_SLAM3"))
    parser.add_argument("--build", type=Path, default=Path("/opt/loop-detector/orb_dbow2-build"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    lock = json.loads((root.parent / "orb_slam3/upstream.lock.json").read_text())["orb_slam3"]
    installed = json.loads((args.source / "evaluation-build.json").read_text())
    if installed["revision"] != lock["revision"]:
        raise ValueError("Installed upstream revision differs from pinned source")
    artifacts = [args.source / name for name in ("Vocabulary/ORBvoc.txt", "Examples/Stereo-Inertial/EuRoC.yaml", "Thirdparty/DBoW2/lib/libDBoW2.so")]
    for path in artifacts:
        if digest(path) != installed["artifacts"][str(path)]:
            raise ValueError(f"Installed artifact changed: {path}")
    subprocess.run(["cmake", "-S", str(root / "native"), "-B", str(args.build), f"-DORB_SOURCE={args.source}", "-DCMAKE_BUILD_TYPE=Release"], check=True)
    subprocess.run(["cmake", "--build", str(args.build), "-j", "2"], check=True)
    dependency_text = subprocess.check_output(["ldd", str(args.build / "orb_dbow2")], text=True)
    if any(name in dependency_text for name in ("libORB_SLAM3", "libg2o", "libpango")):
        raise ValueError("Retrieval binary unexpectedly links the full SLAM pipeline")
    sources = list((root / "native").glob("*")) + [Path(__file__), args.source / "src/ORBextractor.cc", args.source / "include/ORBextractor.h", args.source / "include/ORBVocabulary.h"]
    sources += list((args.source / "Thirdparty/DBoW2/DBoW2").glob("*.h"))
    # Gate every build on parity with actual installed upstream Frame methods.
    sys.path.insert(0, str(root.parents[1]))
    from benchmarks.orb_dbow2.verify import verify
    verification = verify(args.source, args.build)
    files = artifacts + sources + [args.build / "orb_dbow2", args.build / "verification.json", root / "verify.py"]
    manifest = {"schema_version": 1, "benchmark_type": "image_retrieval", "upstream": lock,
                "artifacts": {str(path): digest(path) for path in files}, "runtime_dependencies": dependency_text,
                "compiler": subprocess.check_output(["c++", "--version"], text=True).splitlines()[0],
                "preprocessing": "Pinned EuRoC IMU_STEREO cam0 rectification; native Settings accessor behavior preserved",
                "verification": verification}
    (args.build / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
