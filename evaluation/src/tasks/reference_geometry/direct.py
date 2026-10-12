"""Evaluate reported correspondences against simulator geometry, without pose fitting."""

import json
import shutil
from collections import Counter
from pathlib import Path
from uuid import uuid4

import numpy as np

from ldo.configuration import build_detector, load_config
from tasks.loop_closure.comparison.cli import publish_report
from tasks.loop_closure.comparison.metrics import read_trace
from tasks.loop_closure.comparison.reference import sha256, write_json
from tasks.loop_closure.revisits.metrics import evaluate

from .dataset import frames
from .depth_coverage import summarize
from .detectors import FeaturePairs, run_ldo, run_orb, validate_native
from .direct_report import aggregate
from .geometry import backproject, check_features, decode_depth, sample_depth

ROOT = Path(__file__).resolve().parents[4]


def local(value):
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def validate_manifest(manifest, config, config_path):
    if (
        manifest["configuration_sha256"] != sha256(config_path)
        or manifest["protocol"] != config["protocol"]
    ):
        raise ValueError("Frozen reference configuration differs")
    if manifest["dataset"] != config["dataset"]:
        raise ValueError("Frozen dataset selection differs")
    if manifest["reference_geometry_code_sha256"] != sha256(
        Path(__file__).with_name("geometry.py")
    ):
        raise ValueError("Reference geometry changed after freezing")
    if [s["trajectory"] for s in manifest["sequences"]] != config["dataset"]["trajectories"]:
        raise ValueError("Reference does not cover the declared trajectories")


def load_sequence(info):
    root = Path(info["root"])
    for name, key in (
        ("frames.json", "frames_sha256"),
        ("reference.jsonl", "reference_sha256"),
        ("events.json", "events_sha256"),
    ):
        if sha256(root / name) != info[key]:
            raise ValueError(f"Frozen reference artifact changed: {name}")
    items = frames(root)
    for item in items:
        for field in ("image", "depth"):
            if sha256(Path(item[field])) != item[field + "_sha256"]:
                raise ValueError(f"Frozen reference input changed: {field}")
    reference = {}
    for line in (root / "reference.jsonl").read_text().splitlines():
        row = json.loads(line)
        reference[row["query_timestamp_ns"], row["historical_timestamp_ns"]] = row
    events = json.loads((root / "events.json").read_text())
    return items, reference, events


def feature_records(method, q, h, assignments, qp, hp, qd, hd, qpose, hpose, policy):
    """One verdict per original reported assignment, with explicit world coordinates."""
    checked = check_features(qp, hp, qd, hd, np.linalg.inv(hpose) @ qpose, policy)
    qz, qvalid = sample_depth(qd, qp, policy)
    hz, hvalid = sample_depth(hd, hp, policy)
    qw = backproject(qp, qz) @ qpose[:3, :3].T + qpose[:3, 3]
    hw = backproject(hp, hz) @ hpose[:3, :3].T + hpose[:3, 3]
    records = []
    for i, (qi, hi) in enumerate(assignments):
        records.append(
            {
                "method": method,
                "query_timestamp_ns": q,
                "historical_timestamp_ns": h,
                "query_feature_id": int(qi),
                "historical_feature_id": int(hi),
                "query_pixel": qp[i].tolist(),
                "historical_pixel": hp[i].tolist(),
                "query_world_xyz_m": qw[i].tolist() if qvalid[i] else None,
                "historical_world_xyz_m": hw[i].tolist() if hvalid[i] else None,
                "query_reference_depth_valid": bool(qvalid[i]),
                "historical_reference_depth_valid": bool(hvalid[i]),
                "verdict": str(checked["verdicts"][i]),
                "xyz_error_m": float(checked["xyz_error_m"][i])
                if qvalid[i] and hvalid[i]
                else None,
                "symmetric_pixel_error": float(checked["pixel_error"][i])
                if np.isfinite(checked["pixel_error"][i]) and qvalid[i] and hvalid[i]
                else None,
            }
        )
    return checked["counts"], records


def evaluate_saved(config, config_path, evidence_path):
    """Recompute from model features, never from previous verifier decisions or masks."""
    source = json.loads(evidence_path.read_text())
    source_task = source["reference_geometry"]
    manifest, policy = source_task["manifest"], config["protocol"]
    validate_manifest(manifest, config, config_path)
    evidence_root = Path(
        source_task["detector_evidence_directory"]
        if source_task.get("mode") == "reference_features"
        else source_task["artifact_directory"]
    )
    by_trajectory = {s["trajectory"]: s for s in source_task["sequences"]}
    if set(by_trajectory) != set(config["dataset"]["trajectories"]):
        raise ValueError("Detector evidence does not cover every declared trajectory")
    output = local(config["output"]) / f"tartanair_reference_features_{uuid4().hex}"
    output.mkdir(parents=True, exist_ok=False)
    snapshot = output / "source"
    snapshot.mkdir()
    for path in Path(__file__).parent.glob("*.py"):
        shutil.copyfile(path, snapshot / path.name)
    shutil.copyfile(config_path, output / "config.yaml")
    result = {
        "sequence": source["sequence"],
        "retrieval": {},
        "claim_validated": False,
        "claim_status": "Direct reference-depth correspondence evaluation; short synthetic pilot, no overall superiority claim.",
        "reference_geometry": {
            "mode": "reference_features",
            "manifest": manifest,
            "artifact_directory": str(output),
            "detector_evidence_directory": str(evidence_root),
            "evidence_summary_sha256": sha256(evidence_path),
            "operational_verifier_used": False,
            "stereo_estimator_used": False,
            "pose_estimation_used": False,
            "ground_truth_enters_detector": False,
            "sequences": [],
            "model_manifest": source_task.get("model_manifest"),
            "orb_build_manifest_sha256": source_task.get("orb_build_manifest_sha256"),
            "source_sha256": {p.name: sha256(p) for p in Path(__file__).parent.glob("*.py")},
        },
    }
    task = result["reference_geometry"]
    for info in manifest["sequences"]:
        trajectory = info["trajectory"]
        items, reference, events = load_sequence(info)
        queries = [f["timestamp_ns"] for f in items]
        images = {f["timestamp_ns"]: Path(f["image"]) for f in items}
        depths = {f["timestamp_ns"]: decode_depth(f["depth"]) for f in items}
        poses = {f["timestamp_ns"]: np.asarray(f["pose"]) for f in items}
        traces, features, trace_hashes = {}, {}, {}
        for method in ("orb", "ldo"):
            path = evidence_root / trajectory / method / "retrieval.jsonl"
            expected = by_trajectory[trajectory]["artifact_hashes"][f"{method}_trace"]
            if sha256(path) != expected:
                raise ValueError("Original detector trace changed")
            trace_hashes[f"{method}_trace"] = expected
            traces[method] = read_trace(path, queries, policy["exclusion_ns"], policy["top_k"])
            features[method] = FeaturePairs(path.parent, method, images)
        directory = output / trajectory
        directory.mkdir()
        totals = {
            name: Counter({key: 0 for key in ("supported", "contradicted", "untestable")})
            for name in traces
        }
        zero = Counter()
        feature_path, pair_path = directory / "feature_checks.jsonl", directory / "pairs.jsonl"
        with feature_path.open("x") as fs, pair_path.open("x") as ps:
            for q in queries:
                for method, trace in traces.items():
                    qpoints, _ = features[method].features(q)
                    for candidate in trace[q]:
                        h = candidate["historical_timestamp_ns"]
                        if (q, h) not in reference:
                            raise ValueError("Candidate lacks a frozen reference-universe entry")
                        hpoints, _ = features[method].features(h)
                        ids = features[method].assignments(q, h)
                        counts, records = feature_records(
                            method,
                            q,
                            h,
                            ids,
                            qpoints[ids[:, 0]],
                            hpoints[ids[:, 1]],
                            depths[q],
                            depths[h],
                            poses[q],
                            poses[h],
                            policy,
                        )
                        totals[method].update(counts)
                        zero[method] += int(len(ids) == 0)
                        for record in records:
                            fs.write(json.dumps(record, allow_nan=False) + "\n")
                        ps.write(
                            json.dumps(
                                {
                                    "method": method,
                                    "query_timestamp_ns": q,
                                    "historical_timestamp_ns": h,
                                    "rank": candidate["rank"],
                                    "score": candidate["score"],
                                    "reported_matches": len(ids),
                                    "feature_counts": counts,
                                    "reference": reference[q, h],
                                },
                                allow_nan=False,
                            )
                            + "\n"
                        )
        sequence = {
            "trajectory": trajectory,
            "reference": info,
            "retrieval": {
                str(k): {
                    method: evaluate(reference, trace, queries, events, k)
                    for method, trace in traces.items()
                }
                for k in sorted({1, policy["top_k"]})
            },
            "features": {
                method: {**dict(counts), "zero_match_pairs": zero[method]}
                for method, counts in totals.items()
            },
            "artifact_hashes": {
                "feature_checks": sha256(feature_path),
                "pairs": sha256(pair_path),
                **trace_hashes,
            },
        }
        task["sequences"].append(sequence)
        write_json(directory / "summary.json", sequence)
        print(f"Direct reference evaluation {trajectory}: {dict(totals)}", flush=True)
    task["aggregate"] = aggregate(task["sequences"], policy["top_k"])
    task["depth_coverage"] = summarize(task["sequences"], output, policy)
    write_json(output / "summary.json", result)
    return publish_report(result, local(config["output"]), config_path)


def run(config, config_path, prepared=None):
    """Run image-only detectors, then independently score every reported assignment."""
    from .workflow import prepare

    prepared = prepared or prepare(config, config_path)
    manifest = json.loads((prepared / "manifest.json").read_text())
    validate_manifest(manifest, config, config_path)
    detector_config = load_config(local(config["ldo_config"]))
    policy = config["protocol"]
    if (
        detector_config.top_k != policy["top_k"]
        or detector_config.exclusion_ns != policy["exclusion_ns"]
    ):
        raise ValueError("Model candidate budget or exclusion differs from shared protocol")
    native_source, build, _ = validate_native(local(config["orb_config"]))
    output = local(config["output"]) / f"tartanair_detector_evidence_{uuid4().hex}"
    output.mkdir(parents=True, exist_ok=False)
    detector, model_manifest = build_detector(detector_config)
    sequences = []
    try:
        for info in manifest["sequences"]:
            print(f"Running image-only detector evidence: {info['trajectory']}", flush=True)
            load_sequence(info)
            replay = Path(info["root"])
            directory = output / info["trajectory"]
            directory.mkdir()
            paths = {
                "orb": run_orb(replay, directory / "orb", native_source, build, policy),
                "ldo": run_ldo(detector, model_manifest, replay, directory / "ldo"),
            }
            sequences.append(
                {
                    "trajectory": info["trajectory"],
                    "artifact_hashes": {
                        f"{name}_trace": sha256(path) for name, path in paths.items()
                    },
                }
            )
    finally:
        detector.close()
    summary = output / "summary.json"
    write_json(
        summary,
        {
            "sequence": config["dataset"]["environment"],
            "reference_geometry": {
                "manifest": manifest,
                "artifact_directory": str(output),
                "sequences": sequences,
                "model_manifest": model_manifest,
                "orb_build_manifest_sha256": sha256(build / "manifest.json"),
            },
        },
    )
    return evaluate_saved(config, config_path, summary)
