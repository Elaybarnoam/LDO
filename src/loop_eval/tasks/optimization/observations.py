"""Integrity-checked original model evidence for sequential development experiments."""

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ldo.policies.confidence import candidate_vector
from loop_eval.tasks.loop_closure.comparison.reference import sha256
from loop_eval.tasks.loop_closure.revisits.metrics import evaluate


@dataclass
class Pair:
    trajectory: str
    q: int
    h: int
    rank: int
    retrieval_score: float
    best_score: float
    historical_count: int
    scores: np.ndarray
    verdicts: np.ndarray
    label: str

    def vector(self, threshold):
        return candidate_vector(
            self.retrieval_score,
            self.best_score,
            self.scores[self.scores > np.float32(threshold)],
            self.historical_count,
        )


def read_summary(path):
    source = json.loads(Path(path).read_text())
    return source.get("comparison_result", source)


def load(path, method="ldo", trajectories=None):
    if method != "ldo":
        raise ValueError("Optimization score sweeps require original LightGlue scores")
    task = read_summary(path)["reference_geometry"]
    artifact = Path(task["artifact_directory"])
    detector = Path(task["detector_evidence_directory"])
    pairs, contexts = [], {}
    for sequence in task["sequences"]:
        trajectory = sequence["trajectory"]
        if trajectories is not None and trajectory not in trajectories:
            continue
        info = sequence["reference"]
        replay = Path(info["root"])
        for name, key in (
            ("frames.json", "frames_sha256"),
            ("reference.jsonl", "reference_sha256"),
            ("events.json", "events_sha256"),
        ):
            if sha256(replay / name) != info[key]:
                raise ValueError("Reference evidence changed")
        refs = {}
        for line in (replay / "reference.jsonl").read_text().splitlines():
            r = json.loads(line)
            refs[r["query_timestamp_ns"], r["historical_timestamp_ns"]] = r
        items = json.loads((replay / "frames.json").read_text())
        queries = [r["timestamp_ns"] for r in items]
        feature_file = artifact / trajectory / "feature_checks.jsonl"
        pair_file = artifact / trajectory / "pairs.jsonl"
        if (
            sha256(feature_file) != sequence["artifact_hashes"]["feature_checks"]
            or sha256(pair_file) != sequence["artifact_hashes"]["pairs"]
        ):
            raise ValueError("Direct evaluation evidence changed")
        groups = {}
        for line in feature_file.read_text().splitlines():
            r = json.loads(line)
            if r["method"] == method:
                groups.setdefault(
                    (r["query_timestamp_ns"], r["historical_timestamp_ns"]), []
                ).append(r)
        metadata = (
            json.loads(
                (detector / trajectory / method / "learned_features/manifest.json").read_text()
            )
            if method == "ldo"
            else None
        )
        traces = {q: [] for q in queries}
        raw = []
        feature_counts = {}
        for line in pair_file.read_text().splitlines():
            r = json.loads(line)
            if r["method"] != method:
                continue
            q, h = r["query_timestamp_ns"], r["historical_timestamp_ns"]
            rows = groups.get((q, h), [])
            path = detector / trajectory / method / "learned_features" / f"pair_{q}_{h}.npz"
            if sha256(path) != metadata["pairs"][path.name]["sha256"]:
                raise ValueError("Model assignment changed")
            with np.load(path, allow_pickle=False) as data:
                ids, scores = data["indices"].copy(), data["scores"].copy()
            if ids.tolist() != [[v["query_feature_id"], v["historical_feature_id"]] for v in rows]:
                raise ValueError("Verdict and score assignments differ")
            feature_path = path.parent / f"{h}_cam0.npz"
            if h not in feature_counts:
                if sha256(feature_path) != metadata["exports"][feature_path.name]["sha256"]:
                    raise ValueError("Historical model features changed")
                with np.load(feature_path, allow_pickle=False) as data:
                    feature_counts[h] = len(data["points"])
            count = feature_counts[h]
            raw.append(
                (
                    q,
                    h,
                    r["rank"],
                    r["score"],
                    count,
                    scores,
                    np.array([v["verdict"] for v in rows]),
                    r["reference"]["label"],
                )
            )
            traces[q].append({"rank": r["rank"], "score": r["score"], "historical_timestamp_ns": h})
        best = {q: max((r["score"] for r in v), default=0.0) for q, v in traces.items()}
        pairs.extend(
            Pair(trajectory, q, h, rank, score, best[q], count, scores, verdicts, label)
            for q, h, rank, score, count, scores, verdicts, label in raw
        )
        contexts[trajectory] = {
            "queries": queries,
            "reference": refs,
            "events": json.loads((replay / "events.json").read_text()),
            "traces": traces,
            "info": info,
            "features_root": str(detector / trajectory / method / "learned_features"),
        }
    return pairs, contexts


def measure(pairs, contexts, threshold=0.1, policy=None, trajectories=None):
    pairs = [r for r in pairs if trajectories is None or r.trajectory in trajectories]
    selected = {name: set() for name in contexts if trajectories is None or name in trajectories}
    counts = Counter({key: 0 for key in ("supported", "contradicted", "untestable")})
    zero = 0
    for row in pairs:
        if policy is not None and policy.score(row.vector(threshold)) < policy.threshold:
            continue
        selected[row.trajectory].add((row.q, row.h))
        mask = row.scores > np.float32(threshold)
        counts.update(row.verdicts[mask].tolist())
        zero += int(not mask.any())
    judged = counts["supported"] + counts["contradicted"]
    total = sum(counts.values())
    values = [
        evaluate(
            contexts[name]["reference"],
            contexts[name]["traces"],
            contexts[name]["queries"],
            contexts[name]["events"],
            5,
            accepted=accepted,
        )
        for name, accepted in selected.items()
    ]
    return {
        "features": {
            **dict(counts),
            "reported": total,
            "judgeable_fraction": judged / total if total else None,
            "supported_among_judgeable": counts["supported"] / judged if judged else None,
            "supported_fraction_bounds": [
                counts["supported"] / total,
                (counts["supported"] + counts["untestable"]) / total,
            ]
            if total
            else None,
        },
        "candidates": {
            key: sum(v[key] for v in values)
            for key in (
                "returned_pairs",
                "true_positive_pairs",
                "false_positive_pairs",
                "unknown_pairs",
                "confirmed_events",
                "detected_confirmed_events",
            )
        },
        "zero_match_pairs": zero,
    }


def change(previous, current):
    a, b = previous["features"], current["features"]
    x, y = previous["candidates"], current["candidates"]
    return {
        "supported_match_retention": b["supported"] / a["supported"] if a["supported"] else None,
        "contradicted_matches_removed": a["contradicted"] - b["contradicted"],
        "true_candidate_retention": y["true_positive_pairs"] / x["true_positive_pairs"]
        if x["true_positive_pairs"]
        else None,
        "false_candidates_removed": x["false_positive_pairs"] - y["false_positive_pairs"],
        "confirmed_event_retention": y["detected_confirmed_events"] / x["detected_confirmed_events"]
        if x["detected_confirmed_events"]
        else None,
    }
