"""Install a pinned, instrumented native build outside timed evaluation runs."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import tarfile
import urllib.request

from patch_source import apply


HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent


def sha256(path):
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def run(command):
    print("Running:", " ".join(map(str, command)), flush=True)
    subprocess.run(list(map(str, command)), check=True)


def source_archive(spec, cache, supplied=None):
    archive = supplied or cache
    if not archive.exists():
        archive.parent.mkdir(parents=True, exist_ok=True)
        ref = "refs/tags/" + spec["tag"] if "tag" in spec else spec["revision"]
        url = spec["repository"].replace("https://github.com/", "https://codeload.github.com/") + "/tar.gz/" + ref
        print("Downloading:", url, flush=True)
        urllib.request.urlretrieve(url, archive)
    if sha256(archive) != spec["archive_sha256"]:
        raise ValueError(f"Source archive checksum mismatch: {archive}")
    return archive


def extract(archive, destination):
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive) as source:
        for member in source.getmembers():
            # Remove the GitHub archive's top-level directory; reject escaping members.
            parts = Path(member.name).parts
            if len(parts) < 2:
                continue
            member.name = str(Path(*parts[1:]))
            source.extract(member, destination, filter="data")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix", type=Path, default=Path("/opt/loop-detector"))
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--orb-archive", type=Path)
    parser.add_argument("--pangolin-archive", type=Path)
    parser.add_argument("--install-dependencies", action="store_true")
    parser.add_argument("--refresh-instrumentation", action="store_true",
                        help="Reapply checked hooks to the same pinned source, reusing compiled dependencies")
    args = parser.parse_args()
    if os.name != "posix" or args.jobs < 1:
        parser.error("Run in Linux with a positive --jobs value")
    if args.install_dependencies:
        run(["apt-get", "update"])
        run(["apt-get", "install", "-y", "build-essential", "cmake", "pkg-config", "libopencv-dev",
             "libeigen3-dev", "libboost-serialization-dev", "libssl-dev", "libglew-dev",
             "libgl1-mesa-dev", "libx11-dev", "libxxf86vm-dev", "libjpeg-dev", "libpng-dev"])
    lock = json.loads((PACKAGE / "upstream.lock.json").read_text())
    root, pangolin = args.prefix / "ORB_SLAM3", args.prefix / "Pangolin"
    receipt = root / "evaluation-source.json"
    patch_hashes = {str(path.relative_to(PACKAGE)): sha256(path) for path in
                    [HERE / "patch_source.py", *sorted((PACKAGE / "instrumentation").glob("EvaluationEvents.*"))]}
    identity = {"lock": lock, "patch_sources": patch_hashes}
    refreshing = args.refresh_instrumentation and receipt.exists()
    if receipt.exists():
        previous = json.loads(receipt.read_text())
        if previous != identity and not refreshing:
            raise ValueError("Installation patches changed; build into a fresh --prefix")
        if refreshing:
            if any(previous["lock"][name] != lock[name] for name in ("orb_slam3", "pangolin")):
                raise ValueError("Instrumentation refresh cannot change dependency revisions")
            previous_build = json.loads((root / "evaluation-build.json").read_text())
            for name, expected in previous_build["artifacts"].items():
                if sha256(Path(name)) != expected:
                    raise ValueError(f"Existing native artifact changed: {name}")
            archive = source_archive(lock["orb_slam3"], args.prefix / "archives/orb.tar.gz", args.orb_archive)
            names = {"CMakeLists.txt", "src/KeyFrame.cc", "src/LoopClosing.cc", "src/LocalMapping.cc",
                     "src/System.cc", "include/Sim3Solver.h", "src/KeyFrameDatabase.cc", "Examples/Stereo-Inertial/stereo_inertial_euroc.cc"}
            restored = set()
            with tarfile.open(archive) as source:
                for member in source:
                    name = "/".join(Path(member.name).parts[1:])
                    if name in names and member.isfile():
                        (root / name).write_bytes(source.extractfile(member).read())
                        restored.add(name)
            if restored != names:
                raise ValueError("Pinned archive is missing files required by instrumentation")
            apply(root, PACKAGE / "instrumentation")
            receipt.write_text(json.dumps(identity, indent=2))
    else:
        orb_archive = source_archive(lock["orb_slam3"], args.prefix / "archives/orb.tar.gz", args.orb_archive)
        pango_archive = source_archive(lock["pangolin"], args.prefix / "archives/pangolin.tar.gz", args.pangolin_archive)
        extract(orb_archive, root)
        extract(pango_archive, pangolin)
        apply(root, PACKAGE / "instrumentation")
        receipt.write_text(json.dumps(identity, indent=2))

    if not refreshing:
        build_dependencies(args, root, pangolin)
    run(["cmake", "--build", root / "build", "--target", "stereo_inertial_euroc", f"-j{args.jobs}"])
    write_manifest(args, lock, root, patch_hashes)


def build_dependencies(args, root, pangolin):
    run(["cmake", "-S", pangolin, "-B", pangolin / "build", "-DCMAKE_BUILD_TYPE=Release",
         "-DBUILD_EXAMPLES=OFF", "-DBUILD_TOOLS=OFF", "-DBUILD_PANGOLIN_PYTHON=OFF",
         "-DBUILD_PANGOLIN_FFMPEG=OFF", "-DCMAKE_CXX_FLAGS=-include cstdint",
         f"-DCMAKE_INSTALL_PREFIX={args.prefix}/pangolin-install"])
    run(["cmake", "--build", pangolin / "build", f"-j{args.jobs}"])
    run(["cmake", "--install", pangolin / "build"])
    run(["cmake", "-S", root / "Thirdparty/DBoW2", "-B", root / "Thirdparty/DBoW2/build", "-DCMAKE_BUILD_TYPE=Release"])
    run(["cmake", "--build", root / "Thirdparty/DBoW2/build", f"-j{args.jobs}"])
    run(["cmake", "-S", root, "-B", root / "build", "-DCMAKE_BUILD_TYPE=Release",
         f"-DCMAKE_PREFIX_PATH={args.prefix}/pangolin-install"])
    # Upstream links g2o by an absolute .so path, which does not establish a
    # CMake target dependency when building a single example target.
    run(["cmake", "--build", root / "build", "--target", "g2o", f"-j{args.jobs}"])


def write_manifest(args, lock, root, patch_hashes):
    vocabulary = root / "Vocabulary/ORBvoc.txt"
    if not vocabulary.exists():
        with tarfile.open(root / "Vocabulary/ORBvoc.txt.tar.gz") as archive:
            archive.extractall(root / "Vocabulary", filter="data")
    binary = root / "Examples/Stereo-Inertial/stereo_inertial_euroc"
    settings = root / "Examples/Stereo-Inertial/EuRoC.yaml"
    artifacts = [binary, settings, vocabulary, root / "lib/libORB_SLAM3.so",
                 root / "Thirdparty/DBoW2/lib/libDBoW2.so", root / "Thirdparty/g2o/lib/libg2o.so"]
    pangolin_lib = args.prefix / "pangolin-install/lib"
    artifacts.extend(sorted(pangolin_lib.glob("libpango*.so")))
    loader_env = os.environ.copy()
    loader_env["LD_LIBRARY_PATH"] = str(pangolin_lib) + os.pathsep + loader_env.get("LD_LIBRARY_PATH", "")
    smoke = subprocess.run([str(binary)], env=loader_env, capture_output=True, text=True)
    if smoke.returncode != 1 or "Usage:" not in smoke.stderr:
        raise RuntimeError(f"Native loader smoke check failed: {smoke.stdout}\n{smoke.stderr}")
    manifest = {"revision": lock["orb_slam3"]["revision"], "instrumentation_version": lock["instrumentation_version"],
                "source_lock": lock, "patch_sources": patch_hashes, "build_recipe_sha256": sha256(Path(__file__)),
                "patches": {name: sha256(root / f"evaluation-{name}.patch") for name in ("instrumentation", "compatibility")},
                "binary_sha256": sha256(binary), "settings_sha256": sha256(settings),
                "artifacts": {str(path): sha256(path) for path in artifacts},
                "platform": platform.platform(), "compiler": subprocess.check_output(["c++", "--version"], text=True),
                "opencv_version": subprocess.check_output(["pkg-config", "--modversion", "opencv4"], text=True).strip(),
                "build": "Release; C++14; original headless EuRoC example; jobs=" + str(args.jobs),
                "pangolin_options": "FFMPEG=OFF; force include cstdint", "seed_control": "not supported by native multi-thread scheduler"}
    (root / "evaluation-build.json").write_text(json.dumps(manifest, indent=2))
    print("Native installation complete:", root / "evaluation-build.json")


if __name__ == "__main__":
    main()
