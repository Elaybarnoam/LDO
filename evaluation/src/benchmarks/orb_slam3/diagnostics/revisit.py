"""Check visual overlap for a historical viewpoint and trace native selection."""

import csv
import hashlib
import json
from pathlib import Path
import shutil

import cv2
import numpy as np


def validate_revisit(trace: Path, sequence: Path, workspace: Path) -> dict:
    truth = sequence / "mav0/state_groundtruth_estimate0/data.csv"
    if not truth.is_file():
        return {"status": "unavailable", "reason": "EuRoC pose ground truth is unavailable"}
    with truth.open() as stream:
        reader = csv.reader(stream)
        next(reader)
        rows = list(reader)
    stamps = np.array([int(row[0]) for row in rows], dtype=np.int64)
    poses = np.array([[float(value) for value in row[1:8]] for row in rows])
    if len(stamps) < 2 or not np.all(np.diff(stamps) > 0) or not np.isfinite(poses).all():
        raise ValueError("Invalid diagnostic ground-truth poses")
    cache = {}

    def pose(stamp):
        if stamp not in cache:
            index = int(np.searchsorted(stamps, stamp))
            choices = [i for i in (index - 1, index) if 0 <= i < len(stamps)]
            index = min(choices, key=lambda i: abs(int(stamps[i]) - stamp))
            cache[stamp] = poses[index] if abs(int(stamps[index]) - stamp) <= 10_000_000 else None
        return cache[stamp]

    candidates = {}
    with trace.open() as stream:
        for line in stream:
            event = json.loads(line)
            if event["event_type"] != "loop_candidate":
                continue
            data = event["payload"]
            qstamp, hstamp = data["query_timestamp_ns"], data["historical_timestamp_ns"]
            if data["candidate_kind"] != "loop" or qstamp - hstamp <= 20_000_000_000:
                continue
            q, h = pose(qstamp), pose(hstamp)
            if q is None or h is None:
                continue
            distance = float(np.linalg.norm(q[:3] - h[:3]))
            cosine = abs(np.dot(q[3:], h[3:])) / (np.linalg.norm(q[3:]) * np.linalg.norm(h[3:]))
            angle = float(np.degrees(2 * np.arccos(np.clip(cosine, 0, 1))))
            if distance >= 1 or angle >= 30:
                continue
            item = candidates.setdefault((qstamp, hstamp), {
                "query_timestamp_ns": qstamp, "historical_timestamp_ns": hstamp,
                "query_keyframe_id": data["query_keyframe_id"], "historical_keyframe_id": data["historical_keyframe_id"],
                "position_distance_m": distance, "orientation_difference_degrees": angle,
                "time_separation_seconds": (qstamp - hstamp) / 1e9, "selection_history": [],
            })
            item["selection_history"].append({"stage": data["selection_stage"], "reason": data["selection_reason"]})
    limits = {"maximum_distance_m": 1, "maximum_angle_degrees": 30, "minimum_separation_seconds": 20,
              "pose_timestamp_tolerance_ms": 10, "maximum_pairs_inspected": 20}
    if not candidates:
        return {"status": "no_candidate_pair", "reason": "No traced historical viewpoint met diagnostic proximity limits",
                "limits": limits}
    cv2.setRNGSeed(0)
    proximity_selection = {}
    for item in candidates.values():
        for outcome in item["selection_history"]:
            counts = proximity_selection.setdefault(outcome["stage"], {})
            reason = outcome["reason"]
            counts[reason] = counts.get(reason, 0) + 1
    orb = cv2.ORB_create(nfeatures=1500)
    matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
    best, best_score = None, -1
    ranked = sorted(candidates.values(), key=lambda item: item["position_distance_m"] + item["orientation_difference_degrees"] / 60)
    for item in ranked[:20]:
        qpath = sequence / f"mav0/cam0/data/{item['query_timestamp_ns']}.png"
        hpath = sequence / f"mav0/cam0/data/{item['historical_timestamp_ns']}.png"
        qi, hi = cv2.imread(str(qpath), cv2.IMREAD_GRAYSCALE), cv2.imread(str(hpath), cv2.IMREAD_GRAYSCALE)
        if qi is None or hi is None:
            raise ValueError("Missing source image for revisit diagnostic")
        qk, qd = orb.detectAndCompute(qi, None)
        hk, hd = orb.detectAndCompute(hi, None)
        matches = [] if qd is None or hd is None else [pair[0] for pair in matcher.knnMatch(qd, hd, k=2)
            if len(pair) == 2 and pair[0].distance < 0.75 * pair[1].distance and pair[0].distance < 50]
        # Keep independent one-to-one image matches; native 3D verification is separate.
        unique = {}
        for match in sorted(matches, key=lambda match: match.distance):
            unique.setdefault(match.trainIdx, match)
        matches = list(unique.values())
        fundamental, homography, coverage = 0, 0, 0.0
        if len(matches) >= 8:
            qp = np.float32([qk[m.queryIdx].pt for m in matches])
            hp = np.float32([hk[m.trainIdx].pt for m in matches])
            _, fm = cv2.findFundamentalMat(qp, hp, cv2.FM_RANSAC, 1.5, 0.999)
            _, hm = cv2.findHomography(qp, hp, cv2.RANSAC, 3.0)
            fundamental = int(fm.sum()) if fm is not None else 0
            homography = int(hm.sum()) if hm is not None else 0
            mask = hm if homography >= fundamental else fm
            if mask is not None:
                inliers = qp[mask.ravel().astype(bool)]
                if len(inliers) > 0:
                    spread = np.ptp(inliers, axis=0)
                    coverage = float(spread[0] * spread[1] / (qi.shape[0] * qi.shape[1]))
        score = max(fundamental, homography)
        supported = len(matches) >= 40 and score >= 25 and coverage >= 0.05
        if supported and score > best_score:
            best_score = score
            best = {**item, "status": "visual_overlap_supported", "feature_matches": len(matches),
                    "fundamental_inliers": fundamental, "homography_inliers": homography,
                    "inlier_image_coverage": coverage, "query_source": str(qpath), "historical_source": str(hpath)}
    if best is None:
        return {"status": "insufficient_visual_evidence", "proximity_pairs": len(candidates), "limits": limits}
    for prefix in ("query", "historical"):
        source = Path(best[f"{prefix}_source"])
        filename = f"revisit_{prefix}_cam0.png"
        shutil.copyfile(source, workspace / filename)
        best[f"{prefix}_image"] = filename
        best[f"{prefix}_image_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    best.update(proximity_pairs=len(candidates), proximity_selection_counts=proximity_selection, limits=limits,
                accuracy_label=False,
                method="Nearest EuRoC body pose; raw cam0 ORB 1500 features; Hamming ratio <0.75 and distance <50; fundamental 1.5px and homography 3px RANSAC. This is visual-overlap evidence, not native 3D verification or an independent loop label.")
    (workspace / "revisit_validation.json").write_text(json.dumps(best, indent=2, allow_nan=False))
    return best
