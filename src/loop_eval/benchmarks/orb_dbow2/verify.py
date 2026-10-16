"""Compare standalone pixels, descriptors, BoW and scores to native Frame methods."""

import argparse
import json
import os
import subprocess
from pathlib import Path

from .build import digest


def verify(source, build):
    work = build / "verification"
    work.mkdir(exist_ok=True)
    camera = Path("/opt/loop-detector/datasets/euroc/MH_01_easy/mav0/cam0/data")
    stamps = [1403636599813555456, 1403636760513555456]
    # Select actual filenames rather than relying on rounded timestamps.
    images = sorted(camera.glob("*.png"))
    selected = [min(images, key=lambda path: abs(int(path.stem) - stamp)) for stamp in stamps]
    replay = work / "pair.tsv"
    replay.write_text("".join(f"{image.stem}\t{image}\n" for image in selected))
    common = [
        str(source / "Vocabulary/ORBvoc.txt"),
        str(source / "Examples/Stereo-Inertial/EuRoC.yaml"),
        str(replay),
    ]
    feature_root = work / "orb_features"
    feature_root.mkdir(exist_ok=True)
    export_env = dict(os.environ, LDO_ORB_FEATURE_DIR=str(feature_root))
    standalone = subprocess.run(
        [str(build / "orb_dbow2"), *common, "20000000000", "5", str(work / "standalone")],
        check=True,
        text=True,
        capture_output=True,
        env=export_env,
    )
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = "/opt/loop-detector/pangolin-install/lib:" + env.get(
        "LD_LIBRARY_PATH", ""
    )
    installed = json.loads((source / "evaluation-build.json").read_text())
    reference_library = source / "lib/libORB_SLAM3.so"
    if digest(reference_library) != installed["artifacts"][str(reference_library)]:
        raise ValueError("Native reference library differs from installed provenance")
    reference = subprocess.run(
        [str(build / "orb_reference"), *common, str(work / "reference")],
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )
    matches = {}
    for image in selected:
        for extension in ("png", "descriptors", "bow"):
            name = f"_{image.stem}.{extension}"
            a, b = work / f"standalone{name}", work / f"reference{name}"
            if a.read_bytes() != b.read_bytes():
                raise ValueError(f"Standalone differs from actual native methods: {name}")
            matches[name] = digest(a)
    for image in selected:
        for camera in ("cam0", "cam1"):
            a = feature_root / f"{image.stem}_{camera}.orb"
            b = work / f"reference_{image.stem}_{camera}.orb"
            if a.read_bytes() != b.read_bytes():
                raise ValueError(f"Native ORB feature export differs: {camera}")
            matches[a.name] = digest(a)
    records = [json.loads(line) for line in standalone.stdout.splitlines()]
    score = records[1]["candidates"][0]["score"]
    expected = float(
        next(
            line.split()[1]
            for line in reference.stdout.splitlines()
            if line.startswith("REFERENCE_SCORE ")
        )
    )
    if score != expected:
        raise ValueError("DBoW2 pair score differs from native vocabulary.score")
    result = {
        "passed": True,
        "reference": "Actual upstream Settings + Frame::ExtractORB + Frame::ComputeBoW + vocabulary.score",
        "binary_sha256": digest(build / "orb_dbow2"),
        "reference_library_sha256": digest(reference_library),
        "timestamps_ns": [int(image.stem) for image in selected],
        "exact_file_matches": matches,
        "pair_score": score,
        "native_reference_score": expected,
    }
    (build / "verification.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path("/opt/loop-detector/ORB_SLAM3"))
    parser.add_argument("--build", type=Path, default=Path("/opt/loop-detector/orb_dbow2-build"))
    args = parser.parse_args()
    verify(args.source, args.build)


if __name__ == "__main__":
    main()
