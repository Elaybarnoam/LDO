"""Render a EuRoC stereo sequence as a viewable MP4."""

import argparse
import csv
import os
from pathlib import Path

import cv2
import numpy as np


def image_rows(camera: Path) -> dict[int, Path]:
    with (camera / "data.csv").open(newline="") as source:
        rows = csv.reader(source)
        next(rows)
        return {int(timestamp): camera / "data" / filename for timestamp, filename in rows}


def read_grayscale(path: Path) -> np.ndarray | None:
    # OpenCV's Windows image loader cannot handle some Unicode directory names.
    return cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sequence", default="MH_01_easy")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    dataset = Path(__file__).parent / "datasets" / "euroc" / args.sequence / "mav0"
    left = image_rows(dataset / "cam0")
    right = image_rows(dataset / "cam1")
    timestamps = sorted(left.keys() & right.keys())
    if not timestamps:
        raise ValueError(f"No synchronized stereo frames in {dataset}")

    sample = read_grayscale(left[timestamps[0]])
    if sample is None:
        raise FileNotFoundError(left[timestamps[0]])
    height, width = sample.shape
    output = args.output or Path(__file__).parent / "output" / f"{args.sequence}_stereo.mp4"
    output.parent.mkdir(parents=True, exist_ok=True)
    original_directory = Path.cwd()
    os.chdir(output.parent)
    writer = cv2.VideoWriter(
        output.name, cv2.VideoWriter_fourcc(*"mp4v"), 20.0, (width * 2, height + 36)
    )
    if not writer.isOpened():
        raise RuntimeError(f"Cannot open video writer for {output}")

    try:
        for index, timestamp in enumerate(timestamps):
            images = [read_grayscale(camera[timestamp]) for camera in (left, right)]
            if any(image is None or image.shape != (height, width) for image in images):
                raise ValueError(f"Missing or differently sized frame at {timestamp}")
            frame = np.zeros((height + 36, width * 2, 3), dtype=np.uint8)
            frame[36:, :width] = cv2.cvtColor(images[0], cv2.COLOR_GRAY2BGR)
            frame[36:, width:] = cv2.cvtColor(images[1], cv2.COLOR_GRAY2BGR)
            elapsed = (timestamp - timestamps[0]) / 1e9
            label = f"{args.sequence}  |  {elapsed:06.2f} s  |  frame {index + 1}/{len(timestamps)}"
            cv2.putText(
                frame,
                label,
                (12, 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )
            cv2.putText(
                frame,
                "cam0",
                (12, 60),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )
            cv2.putText(
                frame,
                "cam1",
                (width + 12, 60),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )
            writer.write(frame)
    finally:
        writer.release()
        os.chdir(original_directory)

    print(f"Rendered {len(timestamps)} stereo frames to {output}")


if __name__ == "__main__":
    main()
