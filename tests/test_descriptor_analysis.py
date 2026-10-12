"""Descriptor probes must distinguish ambiguity from unused compatible edges."""

import numpy as np
import pytest
from tasks.descriptor_analysis.ranking import analyze


def test_good_descriptors_expose_wrong_assignments_without_changing_verdicts():
    descriptors = np.eye(3)
    edges = np.array([[0, 0], [1, 1], [2, 2]])
    indices = np.array([[0, 1], [1, 2], [2, 0]])
    verdicts = np.array(["contradicted"] * 3)
    metrics, evidence = analyze(descriptors, descriptors, edges, indices, verdicts, minimum=3)
    assert metrics["gap_pairs"] == 1
    assert metrics["gap_reciprocal_top1_usable_pairs"] == 1
    assert metrics["contradicted_with_higher_cosine_supported_alternative"] == 3
    assert metrics["missed_supported_queries_top1"] == 3
    assert np.array_equal(evidence["indices"], indices)
    assert np.array_equal(evidence["verdicts"], verdicts)


def test_ambiguous_ties_do_not_invent_top_one_descriptor_separability():
    descriptors = np.ones((3, 2))
    edges = np.array([[0, 0], [1, 1], [2, 2]])
    metrics, values = analyze(descriptors, descriptors, edges, np.empty((0, 2), int), [], minimum=3)
    assert values["forward_ranks"].tolist() == [3, 3, 3]
    assert metrics["reciprocal_top1_capacity"] == 0
    assert metrics["reciprocal_top5_capacity"] == 3
    assert metrics["missed_unassigned_queries"] == 3


def test_reciprocal_rank_restricts_the_same_edge_and_capacity_is_one_to_one():
    # Both query descriptors prefer h0, but h0 prefers q1. The q0/h0 edge is not
    # reciprocal top-one even though q0 has a forward top-one supported edge.
    q = np.array([[1, 0.2], [1, 0]])
    h = np.array([[1, 0], [0, 1]])
    edges = np.array([[0, 0], [1, 0]])
    metrics, _ = analyze(q, h, edges, np.empty((0, 2), int), [], minimum=2)
    assert metrics["forward_top1_capacity"] == 1
    assert metrics["reciprocal_top1_capacity"] == 1
    assert metrics["maximum_supported_capacity"] == 1
    assert metrics["oracle_usable_pairs"] == 0


def test_all_keypoints_compete_including_reference_unknown_alternatives():
    q, h = np.array([[1, 0]]), np.array([[1, 0], [0.9, 0.1]])
    # Only h1 has supported reference geometry. h0 must still compete in ranking.
    metrics, evidence = analyze(q, h, [[0, 1]], np.empty((0, 2), int), [], minimum=1)
    assert evidence["forward_ranks"].tolist() == [2]
    assert metrics["forward_top1_capacity"] == 0
    assert metrics["forward_top5_capacity"] == 1


def test_missing_reference_edges_do_not_turn_unknown_assignments_into_failures():
    metrics, _ = analyze(np.eye(2), np.eye(2), [], [[0, 0]], ["untestable"], minimum=1)
    assert metrics["reported_untestable"] == 1
    assert metrics["reported_contradicted"] == 0
    assert metrics["maximum_supported_capacity"] == 0
    assert metrics["missed_supported_queries"] == 0


@pytest.mark.parametrize("descriptors", [np.zeros((2, 3)), np.full((2, 3), np.nan)])
def test_invalid_descriptors_fail_instead_of_generating_ranks(descriptors):
    with pytest.raises(ValueError):
        analyze(descriptors, descriptors, [], [], [])


def test_misaligned_supported_baseline_is_rejected():
    with pytest.raises(ValueError, match="omits"):
        analyze(np.eye(2), np.eye(2), [[0, 0]], [[1, 1]], ["supported"])
