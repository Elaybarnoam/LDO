"""Replay both detectors through one observation-only operational verifier."""

import json
import shutil
from collections import Counter
from pathlib import Path
from uuid import uuid4

import numpy as np
import yaml

from loop_eval.tasks.feature_matching.xyz.evaluator import read_replay
from loop_eval.tasks.feature_matching.xyz.geometry import ImageGeometry
from loop_eval.tasks.feature_matching.xyz.learned_features import SavedCorrespondences
from loop_eval.tasks.feature_matching.xyz.poses import CameraPoses
from loop_verification.configuration import load_policy
from loop_verification.contracts import VerificationInput
from loop_verification.stereo_depth import StereoDepth, load_stereo_policy
from loop_verification.verifier import LoopVerifier

from .comparison.comparison import compare
from .comparison.metrics import paired_interval, read_trace
from .comparison.reference import load_reference, sha256, verify_images, write_json
from .loop_metrics import query_outcomes, summarize_connections
from .pose_assessment import assess_pose


def load_assessment(path: Path) -> dict:
    p = yaml.safe_load(path.read_text())
    if (
        not isinstance(p, dict)
        or set(p)
        != {
            "version",
            "maximum_translation_error_m",
            "maximum_rotation_error_degrees",
            "threshold_status",
        }
        or p["version"] != 1
        or any(
            type(p[k]) not in (int, float) or not np.isfinite(p[k]) or p[k] <= 0
            for k in ("maximum_translation_error_m", "maximum_rotation_error_degrees")
        )
    ):
        raise ValueError("Invalid independent pose-assessment policy")
    return p


def run_verification(
    config: dict,
    verifier_path: Path,
    stereo_path: Path,
    assessment_path: Path,
    query_limit=None,
    selected_only=False,
    on_event=None,
    on_log=None,
    fixed_root: Path | None = None,
) -> dict:
    root = Path(__file__).resolve().parents[4]
    reference_root = Path(config["reference"]["root"])
    manifest, reference = load_reference(reference_root)
    sequence = Path(config["reference"]["sequence"])
    if config["protocol"] != manifest["protocol"]:
        raise ValueError("Verification protocol differs from reference")
    for filename, expected in manifest["reference_files"].items():
        if sha256(Path(filename)) != expected:
            raise ValueError("Reference inputs changed")
    policy, stereo_policy, assessment = (
        load_policy(verifier_path),
        load_stereo_policy(stereo_path),
        load_assessment(assessment_path),
    )
    output = Path(config["output"]) / f"loop_verification_{uuid4().hex}"
    output.mkdir(parents=True, exist_ok=False)
    snapshots = output / "source"
    snapshots.mkdir()
    code_files = list((root / "src/loop_verification").glob("*.py")) + list(
        (root / "src/stereo_observations").glob("*.py")
    )
    code_files += list(Path(__file__).parent.glob("*.py"))
    for path in code_files + [verifier_path, stereo_path, assessment_path]:
        try:
            relative = path.resolve().relative_to(root)
        except ValueError:
            relative = Path("external_policies") / f"{sha256(path)[:12]}_{path.name}"
        target = snapshots / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    images = read_replay(Path(config["methods"]["orb"]["replay"]))
    traces = {}
    for name, paths in config["methods"].items():
        verify_images(manifest, Path(paths["replay"]))
        traces[name] = read_trace(
            Path(paths["trace"]),
            list(images),
            config["protocol"]["exclusion_ns"],
            max(config["protocol"]["k_values"]),
        )
    if fixed_root:
        fixed = {}
        for line in (fixed_root / "fixed_pairs.jsonl").read_text().splitlines():
            record = json.loads(line)
            fixed[record["query_timestamp_ns"]] = record["candidates"]
        if set(fixed) != set(images):
            raise ValueError("Fixed-pair trace differs from replay")
        traces = {name: fixed for name in ("orb", "ldo")}
    selected = {q["timestamp_ns"] for q in manifest["queries"]}
    poses = CameraPoses(sequence, config["protocol"]["pose_tolerance_ms"])
    admitted_stamps = [q for q in images if poses.get(q) is not None]
    queries = [
        q
        for q in images
        if (not selected_only or q in selected)
        and poses.get(q) is not None
        and admitted_stamps
        and q - admitted_stamps[0] >= config["protocol"]["exclusion_ns"]
    ]
    if query_limit is not None:
        if type(query_limit) is not int or query_limit < 1:
            raise ValueError("Query limit must be positive")
        queries = queries[:query_limit]
    # Match policy is an adapter setting, never an XYZ outcome filter.
    adapter_policy = {"feature_cache_size": 128, "match_ratio": 0.75}
    geometry = {}
    for name, paths in config["methods"].items():
        source_root = (
            fixed_root / "learned_features"
            if fixed_root and name == "ldo"
            else fixed_root / "orb/orb_features"
            if fixed_root
            else Path(paths["trace"]).parent
            / ("learned_features" if name == "ldo" else "orb_features")
        )
        geometry[name] = ImageGeometry(
            sequence,
            adapter_policy,
            source_root,
            SavedCorrespondences(source_root) if name == "ldo" else None,
        )
    stereo = StereoDepth(sequence, stereo_policy, output / "stereo_predictions")
    verifier = LoopVerifier(policy)
    emit = on_event or (lambda name, payload, stamp=None: None)
    log = on_log or (lambda message: None)
    records, excluded = {"orb": [], "ldo": []}, Counter()
    provenance = {
        "verifier_policy": policy,
        "stereo_policy": stereo_policy,
        "assessment_policy": assessment,
        "reference_manifest_sha256": sha256(reference_root / "manifest.json"),
        "source_sha256": {str(p.relative_to(root)): sha256(p) for p in code_files},
        "input_sha256": {str(p): sha256(p) for p in [verifier_path, stereo_path, assessment_path]},
        "scope": {
            "query_limit": query_limit,
            "selected_reference_queries_only": selected_only,
            "processed_query_timestamps": queries,
            "fixed_pairs": bool(fixed_root),
        },
        "runtime_has_reference_inputs": False,
    }
    # Import frozen image-only disparities; no saved world XYZ or pose is read.
    original = Path(config["methods"]["ldo"]["checks"])
    if original.exists():
        old = json.loads((original / "provenance.json").read_text())
        for artifact in (
            Path(stereo_policy["stereo_model_checkpoint"]),
            Path(stereo_policy["stereo_model_source"]) / "ldo-install.json",
        ):
            if old["input_and_code_sha256"].get(str(artifact)) != sha256(artifact):
                raise ValueError("Frozen stereo model provenance differs")
        stereo.use_verified_cache(original.parent / "stereo_correspondences", old["policy"])
        provenance["frozen_stereo_cache"] = str(original.parent / "stereo_correspondences")
    write_json(output / "provenance.json", provenance)
    checked = 0
    try:
        with (
            (output / "pairs.jsonl").open("x") as saved,
            (output / "excluded_pairs.jsonl").open("x") as exclusions,
        ):
            for query in queries:
                for name in ("orb", "ldo"):
                    source = geometry[name]
                    for candidate in traces[name][query]:
                        historical = candidate["historical_timestamp_ns"]
                        admission = poses.eligibility(query, historical)
                        if not admission["eligible"]:
                            excluded[name] += 1
                            exclusions.write(
                                json.dumps(
                                    {
                                        "method": name,
                                        "query_timestamp_ns": query,
                                        "historical_timestamp_ns": historical,
                                        "admission": admission,
                                    }
                                )
                                + "\n"
                            )
                            continue
                        q, h = source.features(images[query]), source.features(images[historical])
                        if source.correspondence_source:
                            matches, _ = source.correspondence_source.assignments(
                                images[query],
                                images[historical],
                                len(q["points"]),
                                len(h["points"]),
                            )
                        else:
                            matches = source.mutual_matches(q["descriptors"], h["descriptors"])
                        assignments = np.array(
                            [(m.queryIdx, m.trainIdx) for m in matches], dtype=np.int64
                        ).reshape(-1, 2)
                        xyz, valid, depth_evidence = stereo.frame(query, images[query], q["points"])
                        observation = VerificationInput(
                            query,
                            historical,
                            assignments,
                            xyz[assignments[:, 0]].copy(),
                            h["points"][assignments[:, 1]].copy(),
                            valid[assignments[:, 0]].copy(),
                            stereo.k.copy(),
                            stereo.distortion.copy(),
                            stereo.size,
                        )
                        verified = verifier.verify(observation)
                        # Reference information enters only after runtime verification.
                        ref, _ = poses.relative(query, historical)
                        item = {
                            "method": name,
                            "query_timestamp_ns": query,
                            "historical_timestamp_ns": historical,
                            "rank": candidate["rank"],
                            "verification": verified.to_dict(),
                            "pose_assessment": assess_pose(
                                verified.transform_historical_from_query, ref, assessment
                            ),
                            "reference_label": reference.get((query, historical), {}).get(
                                "label", "unknown"
                            ),
                            "query_image_sha256": q["sha256"],
                            "historical_image_sha256": h["sha256"],
                            "depth_evidence": depth_evidence,
                        }
                        saved.write(json.dumps(item, allow_nan=False) + "\n")
                        records[name].append(item)
                        emit(
                            "loop_candidate_verified",
                            {
                                "method": name,
                                "status": verified.status,
                                "reason": verified.reason,
                                "query_timestamp_ns": query,
                                "historical_timestamp_ns": historical,
                            },
                            query,
                        )
                        checked += 1
                        if checked % 100 == 0:
                            log(f"Shared loop verifier: {checked} pairs processed")
    finally:
        stereo.close()
    result = compare(
        reference_root,
        {n: {**p, "checks": None} for n, p in config["methods"].items()},
        config["protocol"],
    )
    result["verified_connections"] = {
        "artifact_directory": str(output),
        "pairs_sha256": sha256(output / "pairs.jsonl"),
        "scope": provenance["scope"],
        "assessment_policy": assessment,
        "verifier_policy": policy,
        "excluded_missing_pose": dict(excluded),
        "methods": {n: summarize_connections(items) for n, items in records.items()},
        "query_metrics": {},
        "paired_uncertainty": {},
    }
    # A fixed matching sample is not a detector retrieval experiment.
    evaluated_queries = [] if fixed_root else [q for q in sorted(selected) if q in queries]
    for k in config["protocol"]["k_values"]:
        metrics = {
            n: query_outcomes(reference, items, evaluated_queries, k)
            for n, items in records.items()
        }
        result["verified_connections"]["query_metrics"][str(k)] = metrics
        result["verified_connections"]["paired_uncertainty"][str(k)] = paired_interval(
            metrics["orb"],
            metrics["ldo"],
            config["protocol"]["seed"],
            config["protocol"]["bootstrap_block_queries"],
            config["protocol"]["bootstrap_samples"],
        )
    write_json(output / "summary.json", {"complete": True, **result["verified_connections"]})
    emit("comparison_result", result)
    return result
