"""Reference-labelled descriptor ranks; no model output is modified."""

from collections import Counter

import numpy as np

from loop_eval.tasks.matching_diagnostics.geometry import maximum_assignment


def normalize(descriptors: np.ndarray) -> np.ndarray:
    descriptors = np.asarray(descriptors, dtype=np.float64)
    if descriptors.ndim != 2 or not np.isfinite(descriptors).all():
        raise ValueError("Descriptors must be a finite two-dimensional array")
    norms = np.linalg.norm(descriptors, axis=1, keepdims=True)
    if np.any(norms <= np.finfo(float).tiny):
        raise ValueError("Zero descriptors have undefined cosine similarity")
    return descriptors / norms


def ranks(scores: np.ndarray, pairs: np.ndarray, epsilon: float) -> tuple[np.ndarray, np.ndarray]:
    """Conservative ranks count all competitors tied within epsilon, including self."""
    q, h = pairs.T
    selected = scores[q, h]
    forward = np.sum(scores[q] >= selected[:, None] - epsilon, axis=1)
    reverse = np.sum(scores[:, h].T >= selected[:, None] - epsilon, axis=1)
    return forward.astype(np.int32), reverse.astype(np.int32)


def analyze(
    query_descriptors: np.ndarray,
    history_descriptors: np.ndarray,
    supported_edges: np.ndarray,
    indices: np.ndarray,
    verdicts: np.ndarray,
    budgets: tuple[int, ...] = (1, 5, 10, 50),
    epsilon: float = 1e-7,
    minimum: int = 20,
) -> tuple[dict, dict]:
    qd, hd = normalize(query_descriptors), normalize(history_descriptors)
    if qd.shape[1] != hd.shape[1]:
        raise ValueError("Descriptor dimensions differ")
    if not np.isfinite(epsilon) or epsilon < 0 or minimum < 1:
        raise ValueError("Invalid ranking tolerance or diagnostic minimum")
    if not budgets or any(k < 1 for k in budgets) or tuple(sorted(set(budgets))) != budgets:
        raise ValueError("Rank budgets must be unique increasing positive integers")
    edges = np.asarray(supported_edges, dtype=np.int64).reshape(-1, 2)
    indices = np.asarray(indices, dtype=np.int64).reshape(-1, 2)
    verdicts = np.asarray(verdicts)
    if verdicts.shape != (len(indices),) or not set(verdicts) <= {
        "supported",
        "contradicted",
        "untestable",
    }:
        raise ValueError("Invalid baseline verdicts")
    for pairs in (edges, indices):
        if len(pairs) and (
            np.any(pairs < 0) or pairs[:, 0].max() >= len(qd) or pairs[:, 1].max() >= len(hd)
        ):
            raise ValueError("Feature indices exceed descriptor arrays")
    if any(len(np.unique(indices[:, c])) != len(indices) for c in (0, 1)):
        raise ValueError("Baseline assignments must be one-to-one")
    edge_set = set(map(tuple, edges.tolist()))
    if any(tuple(pair) not in edge_set for pair in indices[verdicts == "supported"]):
        raise ValueError("Geometry graph omits a supported baseline assignment")

    scores = qd @ hd.T
    forward, reverse = ranks(scores, edges, epsilon)
    actual_forward, actual_reverse = ranks(scores, indices, epsilon)
    best_rank = np.full(len(qd), len(hd) + 1, np.int32)
    best_cosine = np.full(len(qd), -np.inf)
    np.minimum.at(best_rank, edges[:, 0], forward)
    np.maximum.at(best_cosine, edges[:, 0], scores[edges[:, 0], edges[:, 1]])
    eligible = np.isfinite(best_cosine)
    actual_supported = np.zeros(len(qd), bool)
    actual_supported[indices[verdicts == "supported", 0]] = True
    missed = eligible & ~actual_supported
    assigned = np.zeros(len(qd), bool)
    assigned[indices[:, 0]] = True
    capacity = len(maximum_assignment(edges, len(qd), len(hd)))
    counts = Counter(
        {
            f"reported_{k}": int(np.sum(verdicts == k))
            for k in ("supported", "contradicted", "untestable")
        }
    )
    counts.update(
        pairs=1,
        supported_queries=int(eligible.sum()),
        missed_supported_queries=int(missed.sum()),
        missed_unassigned_queries=int(np.sum(missed & ~assigned)),
        maximum_supported_capacity=capacity,
        baseline_usable_pairs=int(counts["reported_supported"] >= minimum),
        oracle_usable_pairs=int(capacity >= minimum),
        gap_pairs=int(counts["reported_supported"] < minimum <= capacity),
    )
    gap = bool(counts["gap_pairs"])
    bad = verdicts == "contradicted"
    unknown = verdicts == "untestable"
    has_alternative = eligible[indices[:, 0]]
    better = best_cosine[indices[:, 0]] > scores[indices[:, 0], indices[:, 1]] + epsilon
    counts["contradicted_with_supported_alternative"] = int(np.sum(bad & has_alternative))
    counts["contradicted_with_higher_cosine_supported_alternative"] = int(np.sum(bad & better))
    counts["unknown_with_supported_alternative"] = int(np.sum(unknown & has_alternative))
    for k in budgets:
        forward_edges = forward <= k
        reciprocal_edges = forward_edges & (reverse <= k)
        fc = len(maximum_assignment(edges[forward_edges], len(qd), len(hd)))
        rc = len(maximum_assignment(edges[reciprocal_edges], len(qd), len(hd)))
        counts.update(
            {
                f"forward_top{k}_capacity": fc,
                f"reciprocal_top{k}_capacity": rc,
                f"forward_top{k}_usable_pairs": int(fc >= minimum),
                f"reciprocal_top{k}_usable_pairs": int(rc >= minimum),
                f"gap_forward_top{k}_usable_pairs": int(gap and fc >= minimum),
                f"gap_reciprocal_top{k}_usable_pairs": int(gap and rc >= minimum),
                f"supported_queries_top{k}": int(np.sum(eligible & (best_rank <= k))),
                f"missed_supported_queries_top{k}": int(np.sum(missed & (best_rank <= k))),
                f"reported_supported_forward_top{k}": int(
                    np.sum((verdicts == "supported") & (actual_forward <= k))
                ),
                f"reported_contradicted_forward_top{k}": int(np.sum(bad & (actual_forward <= k))),
            }
        )
    evidence = {
        "supported_edges": edges,
        "forward_ranks": forward,
        "reverse_ranks": reverse,
        "edge_cosines": scores[edges[:, 0], edges[:, 1]],
        "indices": indices,
        "verdicts": verdicts,
        "actual_forward_ranks": actual_forward,
        "actual_reverse_ranks": actual_reverse,
        "actual_cosines": scores[indices[:, 0], indices[:, 1]],
        "query_has_supported_alternative": eligible,
        "query_missed_supported_assignment": missed,
        "query_best_supported_forward_rank": best_rank,
    }
    return dict(counts), evidence
