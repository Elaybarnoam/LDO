"""Check that the deployable detector reproduces the offline-selected policy."""

import json
from pathlib import Path

import numpy as np

from ldo.configuration import build_detector, load_config
from ldo.contracts import KeyframeInput
from ldo.policies.confidence import CandidateConfidencePolicy
from tasks.reference_geometry.dataset import frames

from .develop import ROOT, save
from .heldout import HELDOUT
from .observations import load, read_summary


def main():
    marker = json.loads((HELDOUT / "baseline.json").read_text())
    path = Path(marker["path"])
    pairs, contexts = load(path, trajectories=["P000"])
    trajectory = "P000"
    context = contexts[trajectory]
    config = load_config(ROOT / "ldo/configs/optimized-policy.yaml")
    policy = CandidateConfidencePolicy.from_file(config.policy_parameters)
    expected = {
        (r.q, r.h): r
        for r in pairs
        if r.trajectory == trajectory
        and policy.score(r.vector(config.match_threshold)) >= policy.threshold
    }
    source = read_summary(path)["reference_geometry"]["detector_evidence_directory"]
    source = Path(source) / trajectory / "ldo/learned_features"
    observed, raw_observed = {}, {}
    detector, model_manifest = build_detector(config)

    class AuditedPolicy:
        def __init__(self, wrapped):
            self.wrapped = wrapped
            self.candidates = ()

        def reset(self):
            self.candidates = ()
            self.wrapped.reset()

        def apply(self, query, candidates):
            self.candidates = candidates
            return self.wrapped.apply(query, candidates)

    audit = AuditedPolicy(detector.policy)
    detector.policy = audit
    detector.reset()
    try:
        for item in frames(Path(context["info"]["root"])):
            stamp = item["timestamp_ns"]
            # Exactly the production API: image, integer timestamp and session ID.
            batch = detector.process_keyframe(
                KeyframeInput(str(stamp), stamp, Path(item["image"]), trajectory)
            )
            if [c.rank for c in batch.candidates] != list(range(1, len(batch.candidates) + 1)):
                raise ValueError("Runtime policy returned nonconsecutive candidate ranks")
            for candidate in batch.candidates:
                key = stamp, candidate.historical.timestamp_ns
                observed[key] = candidate.matches
            for candidate in audit.candidates:
                raw_observed[stamp, candidate.historical.timestamp_ns] = candidate.matches
    finally:
        detector.close()
    if set(observed) != set(expected):
        raise ValueError(f"Runtime/offline candidate sets differ: {set(observed) ^ set(expected)}")
    raw_expected = {(r.q, r.h) for r in pairs}
    if set(raw_observed) != raw_expected:
        raise ValueError("Runtime confidence-only candidate identities differ")
    for q, h in raw_expected:
        with np.load(source / f"pair_{q}_{h}.npz", allow_pickle=False) as data:
            mask = data["scores"] > np.float32(config.match_threshold)
            actual = raw_observed[q, h]
            if not np.array_equal(actual.indices, data["indices"][mask]):
                raise ValueError("Runtime/offline reported feature IDs differ")
            if not np.allclose(actual.scores, data["scores"][mask], rtol=0, atol=1e-6):
                raise ValueError("Runtime/offline feature confidences differ")
    result = {
        "passed": True,
        "trajectory": trajectory,
        "candidate_count": len(observed),
        "feature_count": sum(len(value.scores) for value in observed.values()),
        "confidence_only_candidate_count": len(raw_observed),
        "confidence_only_feature_count": sum(len(value.scores) for value in raw_observed.values()),
        "model_manifest": model_manifest,
        "checks": [
            "image-only runtime",
            "candidate identity parity",
            "consecutive ranks",
            "original assignment ID parity",
            "confidence parity within 1e-6",
        ],
    }
    save(HELDOUT / "runtime_verification.json", result)
    print(json.dumps({k: v for k, v in result.items() if k != "model_manifest"}), flush=True)


if __name__ == "__main__":
    main()
