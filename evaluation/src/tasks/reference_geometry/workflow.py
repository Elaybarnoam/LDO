"""Orchestrate independent reference preparation, frozen detectors and reporting."""

import json
import shutil
from collections import Counter
from pathlib import Path
from uuid import uuid4

import numpy as np

from ldo.configuration import build_detector, load_config
from loop_verification.configuration import load_policy
from loop_verification.contracts import VerificationInput
from loop_verification.stereo_depth import StereoDepth, load_stereo_policy
from loop_verification.verifier import LoopVerifier
from tasks.loop_closure.comparison.cli import publish_report
from tasks.loop_closure.comparison.metrics import read_trace
from tasks.loop_closure.comparison.reference import sha256, write_json
from tasks.loop_closure.pose_assessment import assess_pose
from tasks.loop_closure.revisits.metrics import build_events, evaluate, paired_event_uncertainty
from tasks.loop_closure.revisits.operating_points import select
from tasks.loop_closure.verification import load_assessment

from .dataset import audit_stereo, frames, prepare_sequence
from .depth_coverage import summarize as depth_coverage
from .detectors import FeaturePairs, run_ldo, run_orb, validate_native
from .geometry import K, check_features, decode_depth, overlap
from .reporting import aggregate

ROOT = Path(__file__).resolve().parents[4]


def local(value):
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def prepare(config, config_path):
    policy = config["protocol"]
    output = local(config["output"]) / f"tartanair_reference_{uuid4().hex}"
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "config.json", config)
    installation = Path(config["dataset"]["root"]) / "installation.json"
    installed = json.loads(installation.read_text())
    if installed["revision"] != config["dataset"]["revision"]:
        raise ValueError("Installed dataset revision differs")
    sequences = []
    for trajectory in config["dataset"]["trajectories"]:
        replay = output / trajectory
        info = prepare_sequence(config["dataset"], trajectory, replay, policy["frame_stride"])
        items = frames(replay)
        depths = {f["timestamp_ns"]: decode_depth(f["depth"]) for f in items}
        poses = {f["timestamp_ns"]: np.asarray(f["pose"]) for f in items}
        reference = {}
        with (replay / "reference.jsonl").open("x") as stream:
            for qi, query in enumerate(items):
                q = query["timestamp_ns"]
                for historical in items[:qi]:
                    h = historical["timestamp_ns"]
                    if q - h < policy["exclusion_ns"]:
                        continue
                    relative = np.linalg.inv(poses[h]) @ poses[q]
                    evidence = overlap(depths[q], depths[h], relative, policy)
                    reference[q, h] = evidence
                    stream.write(
                        json.dumps(
                            {"query_timestamp_ns": q, "historical_timestamp_ns": h, **evidence}
                        )
                        + "\n"
                    )
        queries = [f["timestamp_ns"] for f in items]
        events = build_events(reference, queries, policy["event_gap_ns"])
        write_json(replay / "events.json", events)
        info.update(
            reference_pairs=len(reference),
            labels=dict(Counter(r["label"] for r in reference.values())),
            reference_events=len(events),
            reference_sha256=sha256(replay / "reference.jsonl"),
            events_sha256=sha256(replay / "events.json"),
        )
        sequences.append(info)
        print(
            f"Prepared {trajectory}: {len(items)} frames, {len(reference)} pairs, {len(events)} reference events; labels {info['labels']}",
            flush=True,
        )
    result = {
        "version": 1,
        "dataset": config["dataset"],
        "protocol": policy,
        "sequences": sequences,
        "configuration_sha256": sha256(config_path),
        "installation_sha256": sha256(installation),
        "reference_geometry_code_sha256": sha256(Path(__file__).with_name("geometry.py")),
        "label_definition": "minimum_bidirectional_visible_surface_overlap_on_fixed_image_grid",
        "static_world_assumption": "provisional_not_independently_certified",
        "pretrained_training_overlap": "not_audited_no_OOD_claim",
        "reference_created_before_detectors": True,
    }
    write_json(output / "manifest.json", result)
    return output


def _reference(path):
    with path.open() as stream:
        return {
            (r["query_timestamp_ns"], r["historical_timestamp_ns"]): r
            for line in stream
            for r in [json.loads(line)]
        }


def run(config, config_path, prepared=None):
    prepared = prepared or prepare(config, config_path)
    manifest = json.loads((prepared / "manifest.json").read_text())
    if (
        manifest["configuration_sha256"] != sha256(config_path)
        or manifest["protocol"] != config["protocol"]
    ):
        raise ValueError("Frozen reference configuration differs")
    if manifest["reference_geometry_code_sha256"] != sha256(
        Path(__file__).with_name("geometry.py")
    ):
        raise ValueError("Reference geometry implementation changed after freezing")
    policy = config["protocol"]
    detector_config = load_config(local(config["ldo_config"]))
    if (
        detector_config.top_k != policy["top_k"]
        or detector_config.exclusion_ns != policy["exclusion_ns"]
    ):
        raise ValueError("Frozen LDO candidate budget/exclusion differs from shared protocol")
    source, build, native_manifest = validate_native(local(config["orb_config"]))
    detector, model_manifest = build_detector(detector_config)
    output = local(config["output"]) / f"tartanair_benchmark_{uuid4().hex}"
    output.mkdir(parents=True, exist_ok=False)
    snapshot = output / "source"
    snapshot.mkdir()
    for path in Path(__file__).parent.glob("*.py"):
        shutil.copyfile(path, snapshot / path.name)
    shutil.copyfile(config_path, output / "config.yaml")
    frozen_configs = {}
    for key in (
        "ldo_config",
        "orb_config",
        "verifier_config",
        "stereo_config",
        "assessment_config",
    ):
        path = local(config[key])
        frozen_configs[key] = {"path": str(path), "sha256": sha256(path)}
        shutil.copyfile(path, output / f"{key}.yaml")
    result = {
        "sequence": config["dataset"]["environment"],
        "retrieval": {},
        "claim_validated": False,
        "claim_status": "Controlled synthetic pilot; geometry-derived labels, no real-world or OOD claim.",
        "reference_geometry": {
            "manifest": manifest,
            "artifact_directory": str(output),
            "sequences": [],
            "model_manifest": model_manifest,
            "orb_build_manifest_sha256": sha256(build / "manifest.json"),
            "frozen_configs": frozen_configs,
            "reference_manifest_sha256": sha256(prepared / "manifest.json"),
            "reference_depth_enters_operational_verifier": False,
            "label_policy_is_scene_identity_proof": False,
        },
        "source_sha256": {p.name: sha256(p) for p in Path(__file__).parent.glob("*.py")},
    }
    assessment = load_assessment(local(config["assessment_config"]))
    result["reference_geometry"]["assessment_policy"] = assessment
    verifier = LoopVerifier(load_policy(local(config["verifier_config"])))
    stereo_policy = load_stereo_policy(local(config["stereo_config"]))
    try:
        for info in manifest["sequences"]:
            trajectory = info["trajectory"]
            replay = Path(info["root"])
            calibration_audit = audit_stereo(config["dataset"], trajectory, policy)
            print(f"Stereo reference audit {trajectory}: {calibration_audit}", flush=True)
            for name, expected in (
                ("frames.json", info["frames_sha256"]),
                ("reference.jsonl", info["reference_sha256"]),
                ("events.json", info["events_sha256"]),
            ):
                if sha256(replay / name) != expected:
                    raise ValueError("Frozen reference artifact changed")
            for name, expected in info["replay_inputs_sha256"].items():
                if sha256(replay / name) != expected:
                    raise ValueError("Frozen calibration or timestamp list changed")
            items = frames(replay)
            for frame in items:
                if (
                    sha256(Path(frame["image"])) != frame["image_sha256"]
                    or sha256(Path(frame["depth"])) != frame["depth_sha256"]
                    or sha256(Path(frame["right_image"])) != frame["right_image_sha256"]
                ):
                    raise ValueError("Frozen image or reference depth changed")
            queries = [f["timestamp_ns"] for f in items]
            images = {f["timestamp_ns"]: Path(f["image"]) for f in items}
            depths = {f["timestamp_ns"]: decode_depth(f["depth"]) for f in items}
            poses = {f["timestamp_ns"]: np.asarray(f["pose"]) for f in items}
            reference, events = (
                _reference(replay / "reference.jsonl"),
                json.loads((replay / "events.json").read_text()),
            )
            experiment = output / trajectory
            experiment.mkdir()
            print(f"Running frozen ORB and LDO on {trajectory}", flush=True)
            traces = {
                "orb": run_orb(replay, experiment / "orb", source, build, policy),
                "ldo": run_ldo(detector, model_manifest, replay, experiment / "ldo"),
            }
            traces = {
                name: read_trace(path, queries, policy["exclusion_ns"], policy["top_k"])
                for name, path in traces.items()
            }
            sources = {name: FeaturePairs(experiment / name, name, images) for name in traces}
            counts = {name: Counter() for name in traces}
            accepted, accurate = {n: set() for n in traces}, {n: set() for n in traces}
            pose_errors = {n: [] for n in traces}
            stereo = StereoDepth(
                replay, stereo_policy, experiment / "stereo_predictions", cache_size=len(items) * 2
            )
            feature_path = experiment / "feature_checks.jsonl"
            pair_path = experiment / "connections.jsonl"
            try:
                with feature_path.open("x") as feature_stream, pair_path.open("x") as pair_stream:
                    for q in queries:
                        for name, trace in traces.items():
                            features = sources[name]
                            qpoints, _ = features.features(q)
                            for candidate in trace[q]:
                                h = candidate["historical_timestamp_ns"]
                                hpoints, _ = features.features(h)
                                assignments = features.assignments(q, h)
                                qp, hp = qpoints[assignments[:, 0]], hpoints[assignments[:, 1]]
                                relative = np.linalg.inv(poses[h]) @ poses[q]
                                checked = check_features(
                                    qp, hp, depths[q], depths[h], relative, policy
                                )
                                counts[name].update(checked["counts"])
                                for i, (qi, hi) in enumerate(assignments):

                                    def finite(value):
                                        return float(value) if np.isfinite(value) else None

                                    feature_stream.write(
                                        json.dumps(
                                            {
                                                "method": name,
                                                "query_timestamp_ns": q,
                                                "historical_timestamp_ns": h,
                                                "query_feature_id": int(qi),
                                                "historical_feature_id": int(hi),
                                                "query_pixel": qp[i].tolist(),
                                                "historical_pixel": hp[i].tolist(),
                                                "verdict": str(checked["verdicts"][i]),
                                                "xyz_error_m": finite(checked["xyz_error_m"][i]),
                                                "symmetric_pixel_error": finite(
                                                    checked["pixel_error"][i]
                                                ),
                                            },
                                            allow_nan=False,
                                        )
                                        + "\n"
                                    )
                                # Observation stereo and GT evaluation are deliberately separate.
                                xyz, valid, evidence = stereo.frame(q, images[q], qpoints)
                                observation = VerificationInput(
                                    q,
                                    h,
                                    assignments,
                                    xyz[assignments[:, 0]].copy(),
                                    hp.copy(),
                                    valid[assignments[:, 0]].copy(),
                                    K.copy(),
                                    np.zeros(4),
                                    (640, 640),
                                )
                                verified = verifier.verify(observation)
                                pose = assess_pose(
                                    verified.transform_historical_from_query, relative, assessment
                                )
                                if verified.status == "accepted":
                                    accepted[name].add((q, h))
                                    if pose["within_tolerance"]:
                                        accurate[name].add((q, h))
                                    pose_errors[name].append(pose)
                                pair_stream.write(
                                    json.dumps(
                                        {
                                            "method": name,
                                            "query_timestamp_ns": q,
                                            "historical_timestamp_ns": h,
                                            "rank": candidate["rank"],
                                            "score": candidate["score"],
                                            "reference": reference[q, h],
                                            "feature_counts": checked["counts"],
                                            "verification": verified.to_dict(),
                                            "pose_assessment": pose,
                                            "depth_evidence": evidence,
                                        },
                                        allow_nan=False,
                                    )
                                    + "\n"
                                )
            finally:
                stereo.close()
            metrics = {
                str(k): {
                    name: evaluate(reference, trace, queries, events, k)
                    for name, trace in traces.items()
                }
                for k in (1, policy["top_k"])
            }
            selection = {
                str(k): {
                    name: select(reference, trace, queries, events, k, policy["target_precision"])
                    for name, trace in traces.items()
                }
                for k in (1, policy["top_k"])
            }
            sequence_result = {
                "trajectory": trajectory,
                "calibration_audit": calibration_audit,
                "reference": info,
                "retrieval": metrics,
                "development_selection_only": selection,
                "event_uncertainty": {
                    str(k): paired_event_uncertainty(
                        metrics[str(k)]["orb"], metrics[str(k)]["ldo"], policy["seed"], 3, 2000
                    )
                    for k in (1, policy["top_k"])
                },
                "features": {
                    name: {
                        **dict(c),
                        "judgeable_fraction": (c["supported"] + c["contradicted"]) / sum(c.values())
                        if sum(c.values())
                        else None,
                        "support_among_judgeable": c["supported"]
                        / (c["supported"] + c["contradicted"])
                        if c["supported"] + c["contradicted"]
                        else None,
                    }
                    for name, c in counts.items()
                },
                "connections": {
                    name: {
                        "accepted": len(accepted[name]),
                        "pose_consistent": len(accurate[name]),
                        "pose_inconsistent": len(accepted[name]) - len(accurate[name]),
                        "pose_errors": pose_errors[name],
                        "pose_consistent_independent_reference": evaluate(
                            reference,
                            traces[name],
                            queries,
                            events,
                            policy["top_k"],
                            accepted=accurate[name],
                        ),
                        "independent_reference": evaluate(
                            reference,
                            traces[name],
                            queries,
                            events,
                            policy["top_k"],
                            accepted=accepted[name],
                        ),
                    }
                    for name in traces
                },
                "artifact_hashes": {
                    "feature_checks": sha256(feature_path),
                    "connections": sha256(pair_path),
                    **{
                        f"{name}_trace": sha256(experiment / name / "retrieval.jsonl")
                        for name in traces
                    },
                },
            }
            result["reference_geometry"]["sequences"].append(sequence_result)
            write_json(experiment / "summary.json", sequence_result)
            print(
                f"Completed {trajectory}: reference events={len(events)}, features={sequence_result['features']}",
                flush=True,
            )
    finally:
        detector.close()
    task = result["reference_geometry"]
    task["aggregate"] = aggregate(task["sequences"], policy["top_k"])
    task["depth_coverage"] = depth_coverage(task["sequences"], output, policy)
    write_json(output / "summary.json", result)
    return publish_report(result, local(config["output"]), config_path)
