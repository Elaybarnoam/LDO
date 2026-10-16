"""Small CPU-only demonstration of the production causal detector interface.

The deterministic synthetic adapters exercise orchestration and contracts, not
learned model quality. No dataset, checkpoint, network, stereo, or CUDA is used.
"""

import argparse
import json
import tempfile
from pathlib import Path

import cv2
import numpy as np

from ldo.contracts import CorrespondenceBatch, KeyframeInput, LocalFeatures
from ldo.detector import Detector
from ldo.policies.proposal import RetrievalOrderPolicy


class SyntheticEncoder:
    dimension = 2
    fingerprint = "synthetic-cpu-smoke-v1"

    def encode(self, image: Path):
        return np.array([1.0, 0.0], dtype=np.float32)

    def close(self):
        pass


class SyntheticPairEngine:
    fingerprint = "synthetic-points-v1"

    def extract(self, image: Path):
        return LocalFeatures(
            np.array([[8, 8], [16, 16]], dtype=np.float32),
            np.eye(2, dtype=np.float32),
            np.ones(2, dtype=np.float32),
            (32, 32),
            "synthetic",
            self.fingerprint,
        )

    def match(self, query, history):
        return CorrespondenceBatch(
            np.array([[0, 0], [1, 1]], dtype=np.int64),
            np.ones(2, dtype=np.float32),
            "synthetic_identity",
        )

    def close(self):
        pass


def replay() -> dict:
    with tempfile.TemporaryDirectory(prefix="ldo-smoke-") as folder:
        image = Path(folder) / "synthetic.png"
        if not cv2.imwrite(str(image), np.zeros((32, 32), dtype=np.uint8)):
            raise RuntimeError("Could not write synthetic image")
        detector = Detector(
            SyntheticEncoder(),
            SyntheticPairEngine(),
            RetrievalOrderPolicy(),
            top_k=2,
            exclusion_ns=2_000_000_000,
        )
        rows = []
        try:
            for i in range(4):
                result = detector.process_keyframe(KeyframeInput(str(i), i * 1_000_000_000, image))
                rows.append(
                    {
                        "query": str(i),
                        "eligible": result.eligible_history_count,
                        "candidates": [c.historical.keyframe_id for c in result.candidates],
                        "matches": [len(c.matches.indices) for c in result.candidates],
                    }
                )
        finally:
            detector.close()
    return {
        "schema_version": 1,
        "mode": "synthetic_cpu_smoke",
        "research_result": False,
        "frames": rows,
    }


def main(arguments=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Save the deterministic JSON demonstration")
    args = parser.parse_args(arguments)
    result = replay()
    text = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
