"""One frozen fresh-environment test; no choice is made from test measurements."""

import json
from pathlib import Path

import numpy as np
import yaml

from ldo.artifacts import sha256, write_json
from ldo.configuration import build_detector, load_config
from tasks.loop_closure.comparison.metrics import read_trace
from tasks.loop_closure.revisits.metrics import evaluate
from tasks.reference_depth_v2.geometry import check_features
from tasks.reference_geometry.detectors import FeaturePairs, run_ldo, run_orb, validate_native
from tasks.reference_geometry.direct import load_sequence

from .engine import KEYS, references
from .metrics import measure
from .setup import ROOT


def score_sequence(context, evidence_root, kind, assets, policy, output):
    items, depths, masks, poses, labels, semantic_hashes = references(context, assets)
    features = FeaturePairs(evidence_root, kind, {s: Path(f["image"]) for s, f in items.items()})
    rows = []
    output.mkdir(parents=True, exist_ok=True)
    for pair in context["pairs"]:
        q, h = pair["q"], pair["h"]
        qp, _ = features.features(q)
        hp, _ = features.features(h)
        ids = features.assignments(q, h)
        assessed = check_features(
            qp[ids[:, 0]],
            hp[ids[:, 1]],
            depths[q],
            depths[h],
            masks[q],
            masks[h],
            np.linalg.inv(poses[h]) @ poses[q],
            set(labels.values()),
            labels["sky"],
            policy,
        )
        path = output / f"{q}_{h}.npz"
        np.savez_compressed(
            path,
            indices=ids,
            query_points=qp[ids[:, 0]],
            historical_points=hp[ids[:, 1]],
            **assessed,
        )
        rows.append(
            {
                **pair,
                "environment": context["environment"],
                "trajectory": context["trajectory"],
                "counts": {key: int(np.sum(assessed["verdicts"] == key)) for key in KEYS},
                "evidence": str(path),
                "sha256": sha256(path),
            }
        )
    return rows, semantic_hashes


def run(settings, root):
    development = json.loads((root / "development.json").read_text())
    selected_path = Path(development["selected_configuration"])
    if sha256(selected_path) != development["selected_configuration_sha256"]:
        raise ValueError("Selected production configuration changed")
    marker = root / "test-prepared.json"
    if not marker.exists():
        raise ValueError("Run matching_optimization.setup before the fresh test")
    prepared = json.loads(marker.read_text())
    manifest_path = Path(prepared["root"]) / "manifest.json"
    if sha256(manifest_path) != prepared["sha256"]:
        raise ValueError("Fresh reference manifest changed")
    manifest = json.loads(manifest_path.read_text())
    if manifest["dataset"]["environment"] != settings["test"]["environment"]:
        raise ValueError("Unexpected held-out scene")
    frozen = {
        "development_sha256": sha256(root / "development.json"),
        "selected_configuration_sha256": sha256(selected_path),
        "baseline_configuration_sha256": sha256(root / "baseline.yaml"),
        "reference_manifest_sha256": sha256(manifest_path),
        "experiment_freeze_sha256": sha256(root / "experiment-freeze.json"),
        "selected_before_test": True,
    }
    freeze_path = root / "test-freeze.json"
    if freeze_path.exists() and json.loads(freeze_path.read_text()) != frozen:
        raise ValueError("Choices changed after held-out test freeze")
    write_json(freeze_path, frozen)
    completed = root / "test-results.json"
    if completed.exists():
        return json.loads(completed.read_text())
    assets = json.loads((root / "semantic-assets.json").read_text())
    policy = yaml.safe_load((ROOT / settings["evaluator"]).read_text())
    native, build, native_manifest = validate_native(
        ROOT / "evaluation/src/benchmarks/orb_dbow2/config.yaml"
    )
    protocol = manifest["protocol"]
    evidence = root / "heldout-detectors"
    evidence.mkdir(exist_ok=True)
    method_manifests = {"orb": native_manifest}
    paths = {}
    for method, config_path in (
        ("orb", None),
        ("baseline", root / "baseline.yaml"),
        ("selected", selected_path),
    ):
        if method == "selected" and development["selected"] == development["baseline"]:
            paths[method], method_manifests[method] = (
                paths["baseline"],
                method_manifests["baseline"],
            )
            continue
        detector = None
        if config_path is not None:
            detector, model_manifest = build_detector(load_config(config_path))
            method_manifests[method] = model_manifest
        paths[method] = {}
        try:
            for info in manifest["sequences"]:
                trajectory = info["trajectory"]
                replay = Path(info["root"])
                directory = evidence / method / trajectory
                resume = evidence / f"{method}_{trajectory}.json"
                if resume.exists():
                    saved = json.loads(resume.read_text())
                    trace = Path(saved["trace"])
                    if sha256(trace) != saved["sha256"]:
                        raise ValueError("Held-out detector trace changed")
                else:
                    print(f"Fresh test inference {method}/{trajectory}", flush=True)
                    load_sequence(info)
                    trace = (
                        run_orb(replay, directory, native, build, protocol)
                        if method == "orb"
                        else run_ldo(detector, method_manifests[method], replay, directory)
                    )
                    write_json(resume, {"trace": str(trace), "sha256": sha256(trace)})
                paths[method][trajectory] = trace
        finally:
            if detector is not None:
                detector.close()
    sequences, aggregate = [], {}
    all_rows = {m: [] for m in paths}
    for info in manifest["sequences"]:
        trajectory = info["trajectory"]
        items, reference, events = load_sequence(info)
        queries = [f["timestamp_ns"] for f in items]
        sequence = {"trajectory": trajectory, "methods": {}}
        for method in paths:
            trace = read_trace(
                paths[method][trajectory], queries, protocol["exclusion_ns"], protocol["top_k"]
            )
            pairs = [
                {
                    "q": q,
                    "h": c["historical_timestamp_ns"],
                    "label": reference[q, c["historical_timestamp_ns"]]["label"],
                }
                for q in queries
                for c in trace[q]
            ]
            context = {
                "environment": settings["test"]["environment"],
                "trajectory": trajectory,
                "reference": info,
                "pairs": pairs,
            }
            rows, hashes = score_sequence(
                context,
                paths[method][trajectory].parent,
                "orb" if method == "orb" else "ldo",
                assets,
                policy,
                root / "heldout-checks" / method / trajectory,
            )
            all_rows[method].extend(rows)
            usable = {
                (r["q"], r["h"])
                for r in rows
                if r["counts"]["supported"] >= settings["minimum_correct_matches_per_pair"]
            }
            raw = evaluate(reference, trace, queries, events, protocol["top_k"])
            matched = evaluate(
                reference, trace, queries, events, protocol["top_k"], accepted=usable
            )
            sequence["methods"][method] = {
                "features": measure(rows, settings["minimum_correct_matches_per_pair"]),
                "retrieval": raw,
                "usable_retrieval": matched,
                "trace": str(paths[method][trajectory]),
                "trace_sha256": sha256(paths[method][trajectory]),
                "semantic_sha256": hashes,
            }
            print(
                f"Scored fresh test {method}/{trajectory}: "
                + json.dumps(sequence["methods"][method]["features"]["overall"]),
                flush=True,
            )
        sequences.append(sequence)
    for method in paths:
        rows = [s["methods"][method] for s in sequences]
        aggregate[method] = {
            "features": measure(all_rows[method], settings["minimum_correct_matches_per_pair"]),
            "events": sum(r["retrieval"]["confirmed_events"] for r in rows),
            "raw_event_hits": sum(r["retrieval"]["detected_confirmed_events"] for r in rows),
            "usable_event_hits": sum(
                r["usable_retrieval"]["detected_confirmed_events"] for r in rows
            ),
            "candidate_true": sum(r["retrieval"]["true_positive_pairs"] for r in rows),
            "candidate_false": sum(r["retrieval"]["false_positive_pairs"] for r in rows),
            "candidate_unknown": sum(r["retrieval"]["unknown_pairs"] for r in rows),
        }
    result = {
        "freeze": frozen,
        "sequences": sequences,
        "aggregate": aggregate,
        "model_manifests": method_manifests,
        "manifest": manifest,
        "test_used_for_selection": False,
    }
    write_json(completed, result)
    return result
