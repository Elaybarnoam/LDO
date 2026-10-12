"""Supervision must distinguish absence of evidence from a negative label."""

from pathlib import Path

import numpy as np
import pytest
import yaml

torch = pytest.importorskip("torch")
pytest.importorskip("lightglue")
training = pytest.importorskip("tasks.optimization.training")
assignment_loss, supervision = training.assignment_loss, training.supervision


def test_geometry_supervision_ignores_depth_edges_and_ambiguous_neighbours():
    policy = yaml.safe_load(
        (
            Path(__file__).resolve().parents[1]
            / "evaluation/src/tasks/reference_geometry/config.yaml"
        ).read_text()
    )["protocol"]
    q = np.array([[100.0, 100.0], [200.0, 200.0], [300.0, 300.0], [500.0, 500.0]])
    h = np.array([[100.0, 100.0], [203.5, 200.0], [400.0, 400.0]])
    depth = np.full((640, 640), 4.0, np.float32)
    invalid = depth.copy()
    invalid[299:302, 299:302] = np.nan
    gtq, gth = supervision(q, h, invalid, depth, np.eye(4), policy)
    assert gtq.tolist() == [0, -2, -2, -1]
    assert gth.tolist() == [0, -2, -1]


def test_assignment_nll_does_not_supervise_unknown_as_dustbin():
    values = torch.zeros((1, 4, 4), requires_grad=True)
    gtq = torch.tensor([0, -1, -2])
    gth = torch.tensor([0, -2, -1])
    loss = assignment_loss(values, gtq, gth)
    loss.backward()
    gradient = values.grad[0]
    assert gradient[0, 0] == -0.5
    assert gradient[1, 3] == -0.25 and gradient[3, 2] == -0.25
    assert gradient[2, 3] == 0 and gradient[3, 1] == 0
    assert torch.count_nonzero(gradient) == 3
