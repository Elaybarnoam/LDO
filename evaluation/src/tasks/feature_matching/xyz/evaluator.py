"""Review any detector's saved replay/candidates without changing its output."""

import hashlib
import json
import time
from collections import Counter
from functools import partial
from pathlib import Path

import cv2
import numpy as np
import yaml

from .coverage import empty_breakdown, merge_breakdown
from .geometry import ImageGeometry
from .poses import CameraPoses
from .stereo import StereoGeometry


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_policy(path):
    policy = yaml.safe_load(Path(path).read_text())
    keys = {
        "version",
        "seed",
        "feature_cache_size",
        "match_ratio",
        "minimum_matches",
        "minimum_inliers",
        "minimum_inlier_ratio",
        "contradiction_maximum_inlier_ratio",
        "ground_truth_error_px",
        "homography_error_px",
        "pose_timestamp_tolerance_ms",
        "minimum_translation_m",
        "maximum_examples_per_outcome",
        "stereo_enabled",
        "stereo_pixel_sigma_px",
        "stereo_minimum_depth_m",
        "stereo_maximum_depth_m",
        "stereo_minimum_parallax_degrees",
        "stereo_maximum_reprojection_px",
        "stereo_maximum_relative_depth_sigma",
        "stereo_world_mahalanobis_squared_maximum",
        "stereo_cross_reprojection_px",
        "reference_position_sigma_m",
        "reference_orientation_sigma_degrees",
    }
    string_keys = {
        "stereo_backend",
        "stereo_model_python",
        "stereo_model_source",
        "stereo_model_checkpoint",
    }
    keys |= string_keys | {"stereo_lr_max_error_px"}
    if (
        not isinstance(policy, dict)
        or set(policy) != keys
        or policy["version"] != 8
        or type(policy["stereo_enabled"]) is not bool
    ):
        raise ValueError("Invalid candidate checker config schema")
    if policy["stereo_backend"] not in {"orb_mutual", "fast_foundationstereo"} or any(
        not isinstance(policy[k], str) or not policy[k] for k in string_keys
    ):
        raise ValueError("Invalid stereo backend configuration")
    for key in keys - {"version", "stereo_enabled"} - string_keys:
        value = policy[key]
        if type(value) not in (int, float) or not np.isfinite(value):
            raise ValueError(f"Invalid checker parameter: {key}")
        if key != "seed" and value <= 0:
            raise ValueError(f"Checker parameter must be positive: {key}")
    for key in (
        "seed",
        "feature_cache_size",
        "minimum_matches",
        "minimum_inliers",
        "maximum_examples_per_outcome",
    ):
        if type(policy[key]) is not int:
            raise ValueError(f"Checker parameter must be integer: {key}")
    if not 0 <= policy["seed"] < 2**31 or not 1 <= policy["maximum_examples_per_outcome"] <= 10:
        raise ValueError("Invalid checker seed/example budget")
    if any(
        not 0 < policy[key] < 1
        for key in ("match_ratio", "minimum_inlier_ratio", "contradiction_maximum_inlier_ratio")
    ):
        raise ValueError("Checker ratios must lie in (0, 1)")
    if policy["contradiction_maximum_inlier_ratio"] >= policy["minimum_inlier_ratio"]:
        raise ValueError("Checker contradiction/support thresholds overlap")
    if policy["stereo_minimum_depth_m"] >= policy["stereo_maximum_depth_m"]:
        raise ValueError("Invalid stereo depth interval")
    return policy


def read_replay(path):
    images, previous = {}, -1
    for line in Path(path).read_text().splitlines():
        stamp, image = line.split("\t", 1)
        stamp = int(stamp)
        if stamp <= previous:
            raise ValueError("Checker replay must be chronological and unique")
        previous = stamp
        images[stamp] = Path(image)
    if not images:
        raise ValueError("Checker replay is empty")
    return images


def check_trace(
    sequence,
    replay_path,
    trace_path,
    output,
    config_path,
    on_event=None,
    on_log=None,
    feature_root=None,
    correspondence_source=None,
):
    """Publish independent evidence per returned candidate, with full provenance.

    Consumes a standalone retrieval JSONL or the shared publisher events JSONL.
    No ranking, score, BoW, transformer feature or native acceptance feeds the
    classification. The checker reviews returned pairs; it cannot measure FN.
    """
    started = time.monotonic()
    sequence, trace_path, output = Path(sequence), Path(trace_path), Path(output)
    policy = load_policy(config_path)
    images = read_replay(replay_path)
    poses = CameraPoses(sequence, policy["pose_timestamp_tolerance_ms"])
    if correspondence_source is not None and policy["stereo_backend"] != "fast_foundationstereo":
        raise ValueError(
            "Learned observations require the existing dense stereo backend, not ORB stereo matching"
        )
    geometry = ImageGeometry(sequence, policy, feature_root, correspondence_source)
    stereo = StereoGeometry(sequence, geometry, policy) if policy["stereo_enabled"] else None
    output.mkdir(parents=True, exist_ok=False)
    files = [Path(config_path), Path(replay_path), trace_path, sequence / "mav0/cam0/sensor.yaml"]
    files += [
        path
        for path in (
            sequence / "mav0/state_groundtruth_estimate0/data.csv",
            sequence / "mav0/state_groundtruth_estimate0/sensor.yaml",
        )
        if path.exists()
    ]
    if stereo is not None:
        files += [
            path
            for path in (sequence / "mav0/cam1/sensor.yaml", sequence / "mav0/cam1/data.csv")
            if path.exists()
        ]
    files += list(Path(__file__).parent.glob("*.py"))
    files += list((Path(__file__).resolve().parents[5] / "stereo_observations").glob("*.py"))
    if stereo is not None and policy["stereo_backend"] == "fast_foundationstereo":
        files += [
            Path(policy["stereo_model_checkpoint"]),
            Path(policy["stereo_model_source"]) / "ldo-install.json",
        ]
    if geometry.feature_root.is_dir():
        files += sorted(geometry.feature_root.glob("*.orb"))
        files += sorted(geometry.feature_root.glob("*.npz"))
        files += [geometry.feature_root / "manifest.json"]
    provenance = {
        "checker_id": "upstream_orb_stereo_world_geometry_v8",
        "policy": policy,
        "input_and_code_sha256": {str(path): digest(path) for path in files},
        "opencv_version": cv2.__version__,
        "numpy_version": np.__version__,
        "ground_truth_available": poses.available,
        "eligibility_rule": "Both image timestamps must be inside reference-pose coverage and have a pose within the saved timestamp tolerance; excluded pairs are not evaluated",
        "stereo_backend": policy["stereo_backend"],
        "feature_source": "Exported upstream ORB_SLAM3 ORBextractor; mutual Hamming ratio matches",
        "feature_root": str(geometry.feature_root),
        "reference_frames": "T_RCam = T_RSensorTruth * inverse(T_BSensorTruth) * T_BCam; EuRoC q_RS order wxyz",
        "method": "Upstream ORB temporal Hamming matches evaluated correspondence-by-correspondence without RANSAC; configured stereo backend estimates right correspondences, raw calibrated triangulation in cam0 axes, two reference-world XYZ estimates, covariance-weighted 3D discrepancy and bidirectional cross-view reprojection; 2D evidence retained separately",
        "stereo_available": stereo.available if stereo is not None else None,
        "uncertainty_model": "First-order pixel noise propagation + assumed independent isotropic reference position/orientation noise; calibration error and cross-pose correlation are not modeled",
        "accuracy_labels": False,
        "threshold_status": "Provisional diagnostic thresholds; not a frozen paper evaluation protocol",
        "limitation": "Evidence flags, not definitive TP/FP labels. EuRoC pose timing/orientation uncertainty and repeated textures can affect checks. Only retrieved pairs are checked; recall is unavailable.",
    }
    if correspondence_source is not None:
        provenance.update(
            feature_source=correspondence_source.source,
            method="Saved learned temporal correspondences, evaluated by the unchanged version 8 stereo and numerical XYZ checker; no temporal RANSAC or coverage gate",
            model_manifest=correspondence_source.manifest["model_manifest"],
        )
    if stereo is not None and stereo.dense is not None:
        provenance["rectification"] = stereo.dense.preparation_manifest()
        provenance["stereo_preparation_version"] = 2
        provenance["method"] += (
            "; original disparity retained, cropped-out observations recovered independently on an expanded rectified canvas with unchanged depth reliability and numerical XYZ gates"
        )
    (output / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    emit = on_event or (lambda name, payload, stamp=None: None)
    emit("candidate_check_started", {**provenance, "artifacts": str(output)})
    counts, reasons, rank_counts, examples, checked = Counter(), Counter(), {}, {}, 0
    ransac_totals = {
        "raw_matches": 0,
        "retained_matches": 0,
        "rejected_matches": 0,
        "status_counts": {},
    }
    feature_totals = {"supported": 0, "contradicted": 0, "untestable": 0}
    coverage_breakdown = empty_breakdown()
    feature_timings = {"stereo_preparation_and_reprojection": 0.0, "xyz_checks": 0.0}
    stereo_totals = {
        "pairs_with_reliable_stereo": 0,
        "paired_landmarks": 0,
        "consistent_landmarks": 0,
    }
    query_count, previous_query, seen = 0, -1, set()
    excluded_count, exclusion_reasons = 0, Counter()
    try:
        with (
            trace_path.open() as source,
            (output / "pairs.jsonl").open("x") as destination,
            (output / "excluded_pairs.jsonl").open("x") as excluded,
        ):
            for line in source:
                record = json.loads(line)
                if "event_type" in record:
                    if record["event_type"] != "retrieval_query":
                        continue
                    record = record["payload"]
                query = record["query_timestamp_ns"]
                if type(query) is not int or query not in images or query <= previous_query:
                    raise ValueError("Checker trace query order/image differs from replay")
                query_count += 1
                previous_query = query
                for candidate in record["candidates"]:
                    historical, rank = candidate["historical_timestamp_ns"], candidate["rank"]
                    pair = (query, historical)
                    if (
                        type(historical) is not int
                        or historical not in images
                        or historical >= query
                        or pair in seen
                    ):
                        raise ValueError("Checker candidate pair missing/duplicated/nonhistorical")
                    if type(rank) is not int or rank < 1:
                        raise ValueError("Invalid candidate rank")
                    seen.add(pair)
                    eligibility = poses.eligibility(query, historical)
                    if not eligibility["eligible"]:
                        payload = {
                            "query_timestamp_ns": query,
                            "historical_timestamp_ns": historical,
                            "rank": rank,
                            "reason": "reference_pose_required",
                            **eligibility,
                        }
                        excluded.write(json.dumps(payload) + "\n")
                        excluded.flush()
                        emit("candidate_excluded", payload, query)
                        excluded_count += 1
                        exclusion_reasons[payload["reason"]] += 1
                        continue
                    relative, pose_evidence = poses.relative(query, historical)
                    # Fixed seed per pair; the decision never uses detector score.
                    qpose, hpose = poses.get(query), poses.get(historical)
                    on_matches = (
                        partial(
                            stereo.check,
                            query,
                            historical,
                            images[query],
                            images[historical],
                            qpose=qpose[0] if qpose else None,
                            hpose=hpose[0] if hpose else None,
                        )
                        if stereo is not None
                        else None
                    )
                    evidence = geometry.check(
                        images[query],
                        images[historical],
                        relative,
                        policy["seed"],
                        on_matches=on_matches,
                    )
                    r = evidence["ransac"]
                    for target, source in (
                        ("raw_matches", "raw_match_count"),
                        ("retained_matches", "retained_match_count"),
                        ("rejected_matches", "rejected_match_count"),
                    ):
                        ransac_totals[target] += r[source]
                    ransac_totals["status_counts"][r["status"]] = (
                        ransac_totals["status_counts"].get(r["status"], 0) + 1
                    )
                    if stereo is not None:
                        evidence["two_d_outcome"], evidence["two_d_reasons"] = (
                            evidence["outcome"],
                            evidence["reasons"],
                        )
                        evidence["outcome"], evidence["reasons"] = (
                            "feature_evaluated",
                            ["per_correspondence_xyz_verdicts"],
                        )
                        for verdict, count in evidence["stereo"]["feature_counts"].items():
                            feature_totals[verdict] += count
                        for stage, duration in evidence["stereo"]["timings_ms"].items():
                            feature_timings[stage] += duration
                        depth = evidence["stereo"]
                        merge_breakdown(coverage_breakdown, depth["coverage_breakdown"])
                        stereo_totals["pairs_with_reliable_stereo"] += depth.get(
                            "reported_match_count", 0
                        ) > 0 and depth.get("paired_landmarks", 0) >= depth.get(
                            "required_support_matches", 1
                        )
                        stereo_totals["paired_landmarks"] += depth.get("paired_landmarks", 0)
                        stereo_totals["consistent_landmarks"] += depth.get(
                            "consistent_landmarks", 0
                        )
                    payload = {
                        "checker_id": provenance["checker_id"],
                        "query_timestamp_ns": query,
                        "historical_timestamp_ns": historical,
                        "rank": rank,
                        "pose_evidence": pose_evidence,
                        **evidence,
                    }
                    destination.write(json.dumps(payload, allow_nan=False) + "\n")
                    destination.flush()
                    # Full XYZ arrays stay in pairs.jsonl; bounded IPC/report records
                    # carry measurements and the evidence location, not huge arrays.
                    compact = {
                        key: value for key, value in payload.items() if key != "feature_matches"
                    }
                    compact["ransac"] = {
                        k: v
                        for k, v in payload["ransac"].items()
                        if k not in {"inlier_mask", "rejected_feature_pairs"}
                    }
                    if "stereo" in compact:
                        compact["stereo"] = {
                            key: value
                            for key, value in payload["stereo"].items()
                            if key not in {"landmarks", "feature_results"}
                        }
                        compact["landmark_evidence_file"] = str(output / "pairs.jsonl")
                        compact["landmark_evidence_line"] = checked + 1
                    emit("candidate_checked", compact, query)
                    outcome = evidence["outcome"]
                    counts[outcome] += 1
                    reasons.update(evidence["reasons"])
                    rank_counts.setdefault(str(rank), Counter())[outcome] += 1
                    examples.setdefault(outcome, []).append(compact)
                    examples[outcome].sort(
                        key=lambda item: (
                            item["rank"],
                            item["query_timestamp_ns"],
                            item["historical_timestamp_ns"],
                        )
                    )
                    examples[outcome] = examples[outcome][: policy["maximum_examples_per_outcome"]]
                    checked += 1
                    if checked % 100 == 0 and on_log:
                        on_log(f"Independent candidate checker: {checked} pairs reviewed")
    finally:
        if stereo is not None:
            stereo.close()
    if query_count != len(images):
        raise ValueError("Checker trace does not cover complete replay")
    if digest(trace_path) != provenance["input_and_code_sha256"][str(trace_path)]:
        raise ValueError("Detector trace changed during independent evaluation")
    retained_examples = []
    for outcome in ("suspicious", "inconclusive", "overlap_supported", "feature_evaluated"):
        for index, item in enumerate(examples.get(outcome, []), 1):
            q = cv2.imread(str(images[item["query_timestamp_ns"]]), cv2.IMREAD_GRAYSCALE)
            h = cv2.imread(str(images[item["historical_timestamp_ns"]]), cv2.IMREAD_GRAYSCALE)
            sheet = cv2.cvtColor(np.hstack((q, h)), cv2.COLOR_GRAY2BGR)
            border = np.zeros((65, sheet.shape[1], 3), dtype=np.uint8)
            depth = item.get("stereo", {})
            text = f"{outcome} | rank {item['rank']} | feature matches {item['measurements']['match_count']} | 3D consistent {depth.get('consistent_landmarks', 0)}/{depth.get('paired_landmarks', 0)}"
            cv2.putText(border, text, (12, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
            cv2.putText(
                border,
                f"Query {item['query_timestamp_ns']} (left) | History {item['historical_timestamp_ns']} (right)",
                (12, 49),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1,
            )
            path = output / f"example_{outcome}_{index}.png"
            if not cv2.imwrite(str(path), np.vstack((border, sheet))):
                raise RuntimeError("Could not write candidate evidence image")
            retained_examples.append({**item, "image": str(path)})
    summary = {
        "checker_id": provenance["checker_id"],
        "checked_pairs": checked,
        "returned_pairs": len(seen),
        "excluded_pairs": excluded_count,
        "exclusion_reason_counts": dict(exclusion_reasons),
        "outcome_counts": dict(counts),
        "reason_counts": dict(reasons),
        "rank_outcome_counts": rank_counts,
        "evaluation_seconds": time.monotonic() - started,
        "examples": retained_examples,
        "stereo_totals": stereo_totals,
        "ransac_totals": ransac_totals,
        "feature_totals": feature_totals,
        "feature_timings_ms": feature_timings,
        "coverage_breakdown": coverage_breakdown,
        "accuracy_labels": False,
        "artifacts": str(output),
        "complete": True,
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    emit("candidate_check_completed", summary)
    return summary
