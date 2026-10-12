"""Reference capacity must be one-to-one and must preserve the original verdicts."""

import numpy as np
from tasks.matching_diagnostics.geometry import analyze, maximum_assignment
from tasks.matching_diagnostics.promotion import assess_promotion

POLICY = {
    "depth_edge_relative_tolerance": 0.05,
    "feature_pixel_tolerance": 3.0,
    "feature_xyz_tolerance_m": 0.05,
    "feature_xyz_relative_tolerance": 0.005,
}


def assess(q, h, ids, depth=None):
    depth = np.full((640, 640), 5.0) if depth is None else depth
    sem = np.ones((640, 640), np.uint8)
    return analyze(q, h, ids, depth, depth, sem, sem, np.eye(4), {1}, -1, POLICY)


def test_maximum_matching_uses_augmenting_paths_and_never_reuses_a_feature():
    edges = np.array([[0, 0], [0, 1], [1, 0]])
    assignment = maximum_assignment(edges, 2, 2)
    assert len(assignment) == 2
    assert len(set(assignment[:, 1])) == 2
    assert len(maximum_assignment(np.array([[0, 0], [1, 0]]), 2, 1)) == 1


def test_existing_features_expose_missed_associations():
    points = np.array([[200, 200], [240, 240], [280, 280]])
    summary, evidence = assess(points, points, [[0, 1], [1, 2], [2, 0]])
    assert summary["reported"] == {"supported": 0, "contradicted": 3, "untestable": 0}
    assert summary["maximum_supported_one_to_one_matches"] == 3
    assert summary["assigned_query_features_with_unused_supported_alternatives"] == 3
    assert len(evidence["oracle_assignment"]) == 3


def test_absent_reference_depth_remains_unknown():
    points = np.array([[200, 200], [240, 240]])
    summary, _ = assess(points, points, [[0, 0], [1, 1]], np.full((640, 640), np.nan))
    assert summary["reported"]["untestable"] == 2
    assert summary["reported"]["contradicted"] == 0
    assert summary["maximum_supported_one_to_one_matches"] == 0


def test_near_gate_diagnostic_does_not_relabel_failed_matches():
    summary, evidence = assess([[320, 320]], [[323.5, 320]], [[0, 0]])
    assert summary["contradictions_near_geometric_gates"] == 1
    assert summary["reported"]["contradicted"] == 1
    assert evidence["verdicts"].tolist() == ["contradicted"]
    assert summary["maximum_supported_one_to_one_matches"] == 0


def test_empty_assignments_can_still_have_supported_feature_opportunities():
    summary, _ = assess([[320, 320]], [[320, 320]], np.empty((0, 2), np.int64))
    assert summary["reported"]["supported"] == 0
    assert summary["maximum_supported_one_to_one_matches"] == 1
    assert summary["unmatched_query_features_with_supported_alternatives"] == 1


def test_promotion_preserves_event_identity_not_only_event_count():
    baseline = {
        "protocol_sha256": "same",
        "query_count": 10,
        "incorrect_matches": 100,
        "scenes": {"A": {"usable_event_ids": ["a", "b"], "correct_matches": 100}},
    }
    candidate = {
        **baseline,
        "incorrect_matches": 50,
        "scenes": {"A": {"usable_event_ids": ["a", "c"], "correct_matches": 100}},
    }
    decision = assess_promotion(baseline, candidate)
    assert not decision["eligible"]
    assert decision["failures"] == [{"scene": "A", "lost_usable_event_ids": ["b"]}]
    candidate["scenes"]["A"]["usable_event_ids"] = ["a", "b", "c"]
    assert assess_promotion(baseline, candidate)["eligible"]
