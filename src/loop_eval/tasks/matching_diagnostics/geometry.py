"""Measure supported assignment capacity using the unchanged reference evaluator."""

from collections import Counter

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import maximum_bipartite_matching
from scipy.spatial import cKDTree

from loop_eval.tasks.reference_depth_v2.geometry import check_features, sample_surface
from loop_eval.tasks.reference_geometry.geometry import backproject, project


def maximum_assignment(edges: np.ndarray, query_count: int, history_count: int) -> np.ndarray:
    """A keypoint can participate in at most one supported correspondence."""
    if not len(edges):
        return np.empty((0, 2), dtype=np.int64)
    graph = csr_matrix(
        (np.ones(len(edges), dtype=np.int8), (edges[:, 0], edges[:, 1])),
        shape=(query_count, history_count),
    )
    assignment = maximum_bipartite_matching(graph, perm_type="column")
    query = np.flatnonzero(assignment >= 0)
    return np.column_stack([query, assignment[query]]).astype(np.int64)


def finite_quantiles(values: np.ndarray) -> dict:
    values = np.asarray(values)
    values = values[np.isfinite(values)]
    return {
        name: float(np.quantile(values, quantile)) if len(values) else None
        for name, quantile in (("p25", 0.25), ("median", 0.5), ("p75", 0.75), ("p95", 0.95))
    }


def analyze(
    query_points: np.ndarray,
    history_points: np.ndarray,
    indices: np.ndarray,
    query_depth: np.ndarray,
    history_depth: np.ndarray,
    query_semantics: np.ndarray,
    history_semantics: np.ndarray,
    relative: np.ndarray,
    known_labels: set,
    sky_label: int,
    policy: dict,
) -> tuple[dict, dict]:
    """Return measured limits and evidence, without changing any model assignments.

    Oracle edges mean geometrically supported under the fixed policy. They do not
    guarantee unique visual identities, descriptor separability or SLAM success.
    """
    query_points = np.asarray(query_points, dtype=float).reshape(-1, 2)
    history_points = np.asarray(history_points, dtype=float).reshape(-1, 2)
    indices = np.asarray(indices, dtype=np.int64).reshape(-1, 2)
    if np.any(indices < 0) or (
        len(indices)
        and (indices[:, 0].max() >= len(query_points) or indices[:, 1].max() >= len(history_points))
    ):
        raise ValueError("Saved assignment indices exceed the feature arrays")
    if any(len(np.unique(indices[:, col])) != len(indices) for col in (0, 1)):
        raise ValueError("Reported assignments must be one-to-one")

    def assess(q, h):
        return check_features(
            q,
            h,
            query_depth,
            history_depth,
            query_semantics,
            history_semantics,
            relative,
            known_labels,
            sky_label,
            policy,
        )

    reported = assess(query_points[indices[:, 0]], history_points[indices[:, 1]])
    qz, qvalid, qr = sample_surface(
        query_depth, query_semantics, query_points, known_labels, sky_label, policy
    )
    _, hvalid, hr = sample_surface(
        history_depth, history_semantics, history_points, known_labels, sky_label, policy
    )
    mapped = backproject(query_points, qz) @ relative[:3, :3].T + relative[:3, 3]
    projected, forward = project(mapped)
    height, width = history_depth.shape
    inside = forward & (projected[:, 0] >= 0) & (projected[:, 0] <= width - 1)
    inside &= (projected[:, 1] >= 0) & (projected[:, 1] <= height - 1)

    # Every support must pass forward reprojection, so this search cannot miss a
    # supported edge. The full evaluator still checks reverse projection and XYZ.
    candidate_edges = []
    if len(history_points):
        tree = cKDTree(history_points)
        radius = policy["feature_pixel_tolerance"] + 1e-7
        for q in np.flatnonzero(qvalid & inside):
            candidate_edges.extend(
                (q, h) for h in sorted(tree.query_ball_point(projected[q], radius))
            )
    candidate_edges = np.asarray(candidate_edges, dtype=np.int64).reshape(-1, 2)
    candidates = assess(query_points[candidate_edges[:, 0]], history_points[candidate_edges[:, 1]])
    edges = candidate_edges[candidates["verdicts"] == "supported"]
    oracle = maximum_assignment(edges, len(query_points), len(history_points))
    supported = reported["verdicts"] == "supported"
    contradicted = reported["verdicts"] == "contradicted"
    if len(oracle) < int(supported.sum()):
        raise AssertionError("Oracle capacity is below the reported supported assignment")
    edge_set = set(map(tuple, edges.tolist()))
    if any(tuple(pair) not in edge_set for pair in indices[supported]):
        raise AssertionError("Oracle search omitted a reported supported edge")

    xyz_gate = np.maximum(
        policy["feature_xyz_tolerance_m"],
        policy["feature_xyz_relative_tolerance"]
        * np.maximum(reported["query_depth_m"], reported["historical_depth_m"]),
    )
    xyz_ratio = reported["xyz_error_m"] / xyz_gate
    pixel_ratio = reported["pixel_error"] / policy["feature_pixel_tolerance"]
    # A diagnostic band only: these are still contradictions, never supports.
    near = contradicted & (xyz_ratio <= 2) & (pixel_ratio <= 2)
    query_with_alternative = set(edges[:, 0].tolist())
    assigned_query = set(indices[:, 0].tolist())
    supported_query = set(indices[supported, 0].tolist())
    summary = {
        "reported": {
            k: int(np.sum(reported["verdicts"] == k))
            for k in ("supported", "contradicted", "untestable")
        },
        "query_features": len(query_points),
        "historical_features": len(history_points),
        "valid_query_depth_features": int(qvalid.sum()),
        "valid_historical_depth_features": int(hvalid.sum()),
        "query_depth_reasons": dict(Counter(qr.tolist())),
        "historical_depth_reasons": dict(Counter(hr.tolist())),
        "query_features_projecting_inside_history": int(np.sum(qvalid & inside)),
        "supported_edge_count": len(edges),
        "maximum_supported_one_to_one_matches": len(oracle),
        "unmatched_query_features_with_supported_alternatives": len(
            query_with_alternative - assigned_query
        ),
        "assigned_query_features_with_unused_supported_alternatives": len(
            (query_with_alternative & assigned_query) - supported_query
        ),
        "contradictions_near_geometric_gates": int(near.sum()),
        "contradictions_with_large_geometric_residuals": int(np.sum(contradicted & ~near)),
        "contradicted_pixel_error_px": finite_quantiles(reported["pixel_error"][contradicted]),
        "contradicted_xyz_error_m": finite_quantiles(reported["xyz_error_m"][contradicted]),
        "contradicted_xyz_gate_ratio": finite_quantiles(xyz_ratio[contradicted]),
    }
    evidence = {
        "indices": indices,
        "query_points": query_points,
        "historical_points": history_points,
        "reference_projected_history_points": projected,
        "supported_edges": edges,
        "oracle_assignment": oracle,
        "near_geometric_gate": near,
        **reported,
    }
    return summary, evidence
