"""Observation-only selection must preserve pixels and cannot reuse endpoints."""

import numpy as np
import pytest
from tasks.image_pair_matching.metrics import assess

from ldo.matching.image_pairs import select_matches


def test_confidence_selection_preserves_subpixels_and_endpoint_uniqueness():
    q = np.array([[1.25, 2.75], [1.25, 2.75], [3.5, 4.5], [6.5, 7.5]])
    h = np.array([[8.1, 9.2], [10.3, 11.4], [8.1, 9.2], [12.5, 13.6]])
    result = select_matches(q, h, [0.9, 0.8, 0.7, 0.6], 0.2, 1024)
    assert len(result.scores) == 2
    assert np.allclose(result.query_points, [q[0], q[3]])
    assert np.allclose(result.historical_points, [h[0], h[3]])
    assert not result.query_points.flags.writeable


def test_empty_output_remains_an_aligned_empty_pair():
    result = select_matches(np.empty((0, 2)), np.empty((0, 2)), [], 0.2, 1024)
    assert result.query_points.shape == (0, 2)
    assert result.scores.shape == (0,)


def test_match_budget_uses_confidence_and_stable_ties():
    points = np.arange(6).reshape(3, 2)
    result = select_matches(points, points, [0.3, 0.9, 0.9], 0.2, 1)
    assert np.array_equal(result.query_points, points[1:2])


@pytest.mark.parametrize("scores", [[np.nan], [1.5]])
def test_invalid_model_confidence_is_an_error(scores):
    with pytest.raises(ValueError):
        select_matches([[1, 2]], [[3, 4]], scores, 0.2, 1024)


def test_fewer_wrong_matches_cannot_hide_lost_correct_matches_or_unknown_coverage():
    original = {
        "pairs": 10,
        "positive_pairs": 5,
        "supported": 100,
        "contradicted": 100,
        "usable_positive_pairs": 5,
        "precision": 0.5,
        "coverage": 0.8,
    }
    candidate = {
        **original,
        "supported": 80,
        "contradicted": 10,
        "precision": 0.89,
        "coverage": 0.5,
    }
    decision = assess(
        {"overall": original, "scenes": {"A": original}},
        {"overall": candidate, "scenes": {"A": candidate}},
        {"minimum_correct_match_retention": 0.9, "minimum_usable_pair_retention": 0.95},
    )
    assert not decision["passed"]
    assert {f["reason"] for f in decision["failures"]} == {
        "correct_match_retention_below_90_percent",
        "coverage_decreased",
    }
