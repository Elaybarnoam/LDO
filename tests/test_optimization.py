"""Operational confidence filtering and honest unknown/retention accounting."""

import json
from pathlib import Path

import numpy as np
import pytest
import yaml
from tasks.optimization.observations import Pair, change, measure

from ldo.configuration import load_config
from ldo.contracts import Candidate, CorrespondenceBatch, KeyframeInput, LocalFeatures
from ldo.policies.confidence import FEATURE_NAMES, CandidateConfidencePolicy


def parameters():
    return {
        "feature_names": list(FEATURE_NAMES),
        "mean": [0.0] * 6,
        "scale": [1.0] * 6,
        "weights": [10.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        "bias": -5.0,
        "threshold": 0.5,
    }


def test_policy_can_abstain_and_preserves_original_correspondences():
    f = LocalFeatures(
        np.array([[1, 1]], np.float32),
        np.ones((1, 2), np.float32),
        np.ones(1, np.float32),
        (10, 10),
        "fixture",
        "fixture",
    )
    matches = CorrespondenceBatch(
        np.array([[0, 0]], np.int64), np.array([0.7], np.float32), "fixture"
    )
    frame = KeyframeInput("h", 1, Path("h.png"))
    candidates = (Candidate(frame, 1, 0.1, matches, f), Candidate(frame, 2, 0.9, matches, f))
    policy = CandidateConfidencePolicy(parameters())
    returned = policy.apply(frame, candidates)
    assert len(returned) == 1 and returned[0].rank == 1
    assert returned[0].matches is matches and returned[0].retrieval_score == 0.9
    assert policy.apply(frame, candidates[:1]) == ()
    assert policy.apply(frame, ()) == ()


def test_unknown_matches_never_become_errors_and_threshold_is_strict():
    pair = Pair(
        "P000",
        6,
        1,
        1,
        0.9,
        0.9,
        4,
        np.array([0.3, 0.31, 0.9], np.float32),
        np.array(["contradicted", "supported", "untestable"]),
        "loop",
    )
    context = {
        "P000": {
            "queries": [1, 6],
            "reference": {(6, 1): {"label": "loop"}},
            "traces": {1: [], 6: [{"rank": 1, "score": 0.9, "historical_timestamp_ns": 1}]},
            "events": [],
        }
    }
    previous = measure([pair], context, 0.1)
    current = measure([pair], context, 0.3)
    assert current["features"]["supported"] == 1
    assert current["features"]["contradicted"] == 0
    assert current["features"]["untestable"] == 1
    assert current["features"]["supported_fraction_bounds"] == [0.5, 1.0]
    assert change(previous, current)["contradicted_matches_removed"] == 1
    empty = measure([], context)
    assert empty["features"]["supported_among_judgeable"] is None


def test_adapted_checkpoint_requires_hash_and_full_depth(tmp_path):
    source = (
        Path(__file__).resolve().parents[1] / "evaluation/src/tasks/reference_geometry/ldo.yaml"
    )
    data = yaml.safe_load(source.read_text())
    data.update(matcher_checkpoint="weights.pt", matcher_checkpoint_sha256="a" * 64)
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(data))
    with pytest.raises(ValueError, match="full-depth"):
        load_config(path)
    data["matcher_full_depth"] = True
    path.write_text(yaml.safe_dump(data))
    config = load_config(path)
    assert config.matcher_checkpoint == tmp_path / "weights.pt"
    assert config.matcher_checkpoint_sha256 == "a" * 64


def test_policy_rejects_invalid_scale_and_schema(tmp_path):
    values = parameters()
    values["scale"][2] = 0.0
    path = tmp_path / "parameters.json"
    path.write_text(json.dumps(values))
    with pytest.raises(ValueError, match="Invalid"):
        CandidateConfidencePolicy.from_file(path)
