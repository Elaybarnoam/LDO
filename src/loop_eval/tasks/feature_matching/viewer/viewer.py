"""Side-by-side images, exact saved feature matches and checker explanations."""

import argparse
import hashlib
import json
import math
import os
import sys
from pathlib import Path, PurePosixPath

import cv2
import numpy as np

from loop_eval.paths import project_root
from loop_eval.tasks.feature_matching.xyz.geometry import coverage

from .clipboard import copy_text
from .depth_explanation import stereo_details
from .lazy_evidence import PairStore

PROJECT = project_root()
WINDOW = "LDO | Candidate review"
CANVAS_WIDTH, CANVAS_HEIGHT = 1440, 1050
BACKGROUND, SURFACE, BORDER = (20, 20, 20), (30, 30, 30), (55, 55, 55)
TEXT, MUTED, ACCENT = (235, 235, 235), (150, 150, 150), (184, 222, 167)
GROUP_LABELS = {
    "all": "Retrieved candidates",
    "supported": "XYZ supports",
    "not supported": "XYZ does not support",
    "contradicted": "Contradicted features",
    "untestable": "Untestable features",
}
COLORS = {
    "passed": (80, 220, 80),
    "reprojection_failed": (0, 180, 255),
    "xyz_failed": (230, 80, 230),
    "both_failed": (70, 70, 255),
    "not_evaluated": (255, 220, 60),
}


def local_path(value):
    text = str(value)
    if os.name == "nt" and text.startswith("/mnt/") and len(text) > 7 and text[6] == "/":
        text = text[5].upper() + ":/" + text[7:]
    return Path(text)


def latest_checks(project=PROJECT):
    for report_path in sorted(
        (project / "evaluation/output").glob("evaluation_*.json"), reverse=True
    ):
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report.get("status") != "complete":
            continue
        for case in report.get("cases", []):
            review = case.get("candidate_evaluation", {})
            if review.get("status") == "complete":
                path = local_path(review["artifacts"])
                if (path / "pairs.jsonl").is_file():
                    return path
    raise ValueError("No completed report with saved candidate-pair evidence was found")


def landmark_gate(landmark, policy):
    xyz = landmark["mahalanobis_squared"] <= policy["stereo_world_mahalanobis_squared_maximum"]
    values = landmark["cross_reprojection_px"]
    reprojection = all(
        value is not None and np.isfinite(value) and value <= policy["stereo_cross_reprojection_px"]
        for value in values
    )
    if xyz and reprojection:
        return "passed"
    if xyz:
        return "reprojection_failed"
    if reprojection:
        return "xyz_failed"
    return "both_failed"


def number(value, digits=3):
    return "N/A" if value is None else f"{value:.{digits}f}"


def label(canvas, value, x, y, scale=0.5, color=TEXT, width=None):
    """Fit a single line into its allocated region, without overflowing cards."""
    value = str(value)
    if width:
        original = value
        while value and cv2.getTextSize(value, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)[0][0] > width:
            value = value[:-1]
        if value != original:
            value = value[:-3] + "..."
    cv2.putText(canvas, value, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, 1, cv2.LINE_AA)


def rounded_fill(canvas, left, top, right, bottom, radius, color):
    radius = min(radius, (right - left) // 2, (bottom - top) // 2)
    cv2.rectangle(canvas, (left + radius, top), (right - radius, bottom), color, -1)
    cv2.rectangle(canvas, (left, top + radius), (right, bottom - radius), color, -1)
    for x in (left + radius, right - radius):
        for y in (top + radius, bottom - radius):
            cv2.circle(canvas, (x, y), radius, color, -1, cv2.LINE_AA)


def card(canvas, left, top, right, bottom, border=BORDER, radius=16):
    rounded_fill(canvas, left, top, right, bottom, radius, border)
    rounded_fill(canvas, left + 1, top + 1, right - 1, bottom - 1, radius - 1, SURFACE)


def paste_image(canvas, image, x, y):
    height, width = image.shape[:2]
    mask = np.zeros((height, width), np.uint8)
    rounded_fill(mask, 0, 0, width - 1, height - 1, 12, 255)
    roi = canvas[y : y + height, x : x + width]
    alpha = mask[..., None].astype(np.float32) / 255
    roi[:] = (image * alpha + roi * (1 - alpha)).astype(np.uint8)


def support_counts(pair, policy):
    if policy.get("version", 0) >= 4:
        total = pair["measurements"]["match_count"]
        required = math.ceil(total * policy["minimum_inlier_ratio"])
        return total, required, required
    return (
        len(pair.get("stereo", {}).get("landmarks", [])),
        policy["minimum_stereo_landmarks"],
        policy.get("minimum_inliers", 20),
    )


def xyz_rejects_pair(pair, policy):
    stereo = pair.get("stereo", {})
    points = stereo.get("landmarks", [])
    total, depth_required, _ = support_counts(pair, policy)
    if (
        not total
        or len(points) < depth_required
        or (
            policy.get("version", 0) < 7
            and stereo.get("paired_coverage", 0) < policy["minimum_image_coverage"]
        )
    ):
        return False
    passed = sum(
        point["mahalanobis_squared"] <= policy["stereo_world_mahalanobis_squared_maximum"]
        for point in points
    )
    return passed / len(points) <= policy["contradiction_maximum_inlier_ratio"]


def xyz_pair_status(pair, policy, width, height):
    points = pair.get("stereo", {}).get("landmarks", [])
    total, depth_required, pass_required = support_counts(pair, policy)
    if not total or len(points) < depth_required:
        return "insufficient evidence"
    passed = [
        point
        for point in points
        if point["mahalanobis_squared"] <= policy["stereo_world_mahalanobis_squared_maximum"]
    ]
    spatial = (
        min(
            coverage(np.array([point[f"{role}_feature_xy"] for point in passed]), width, height)
            for role in ("query", "historical")
        )
        if passed and policy.get("version", 0) < 7
        else 0
    )
    if (
        len(passed) >= pass_required
        and len(passed) / total >= policy["minimum_inlier_ratio"]
        and (policy.get("version", 0) >= 7 or spatial >= policy["minimum_image_coverage"])
    ):
        return "supported"
    return "rejected" if xyz_rejects_pair(pair, policy) else "ambiguous"


def vector(value):
    return "(" + ", ".join(f"{coordinate:.3f}" for coordinate in value) + ")"


class EvidenceReview:
    def __init__(self, checks, dataset_root):
        self.checks = Path(checks)
        self.dataset_root = Path(dataset_root)
        provenance = json.loads((self.checks / "provenance.json").read_text())
        self.detector_label = provenance.get("model_manifest", {}).get("variant", "ORB + DBoW2")
        self.feature_source = provenance.get("feature_source", "Exported upstream ORB")
        self.policy = provenance["policy"]
        self.retrieval = {}
        trace_keys = [
            key
            for key in provenance["input_and_code_sha256"]
            if PurePosixPath(key.replace("\\", "/")).name == "retrieval.jsonl"
        ]
        if len(trace_keys) == 1:
            trace = local_path(trace_keys[0])
            if not trace.is_file():
                trace = self.checks.parent / "retrieval.jsonl"
            raw = trace.read_bytes()
            if (
                hashlib.sha256(raw).hexdigest()
                != provenance["input_and_code_sha256"][trace_keys[0]]
            ):
                raise ValueError("Retrieval trace differs from saved checker provenance")
            for line in raw.decode().splitlines():
                row = json.loads(line)
                row = row.get("payload", row)
                self.retrieval[row["query_timestamp_ns"]] = row
        self.all_pairs = []
        self.excluded_count = 0
        excluded_path = self.checks / "excluded_pairs.jsonl"
        if excluded_path.is_file():
            with excluded_path.open() as stream:
                self.excluded_count = sum(bool(line.strip()) for line in stream)
        self.pair_store = PairStore(self.checks / "pairs.jsonl")
        self.all_pairs = list(self.pair_store.headers())
        self.excluded_count += self.pair_store.excluded_count
        if not self.all_pairs:
            raise ValueError("No saved candidates in this evidence directory")
        self.pairs = self.all_pairs
        self.images = {}
        replay_keys = [
            name
            for name in provenance["input_and_code_sha256"]
            if PurePosixPath(name.replace("\\", "/")).name == "replay.tsv"
        ]
        if len(replay_keys) != 1:
            raise ValueError("Checker provenance must identify one exact replay.tsv")
        replay = local_path(replay_keys[0])
        if not replay.is_file():
            replay = self.checks.parent / "replay.tsv"
        raw = replay.read_bytes()
        if hashlib.sha256(raw).hexdigest() != provenance["input_and_code_sha256"][replay_keys[0]]:
            raise ValueError("Replay differs from saved checker provenance")
        for line in raw.decode().splitlines():
            stamp, filename = line.split("\t", 1)
            original = local_path(filename)
            if original.is_file():
                resolved = original
            else:
                parts = PurePosixPath(filename.replace("\\", "/")).parts
                if "mav0" not in parts or parts.index("mav0") == 0:
                    raise ValueError(f"Cannot map saved image to installed dataset: {filename}")
                index = parts.index("mav0")
                resolved = self.dataset_root.joinpath(*parts[index - 1 :])
            self.images[int(stamp)] = resolved

    def load_images(self, pair):
        result = []
        for role in ("query", "historical"):
            path = self.images[pair[f"{role}_timestamp_ns"]]
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != pair["measurements"][f"{role}_image_sha256"]:
                raise ValueError(f"Image differs from evaluated image: {path}")
            image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
            if image is None:
                raise ValueError(f"Cannot decode image: {path}")
            result.append(image)
        return result


class PairViewer:
    def __init__(self, review, index=0, group="all"):
        self.review = review
        self.feature_mode = any(
            "feature_results" in pair.get("stereo", {}) for pair in review.all_pairs
        )
        self.index, self.feature = 0, 0
        self.all_lines, self.overlay = (
            review.policy.get("version", 0) >= 7 and not self.feature_mode,
            True,
        )
        self.ids = False
        self._loaded_index, self._images = None, None
        self.dirty = True
        self.image_boxes = []
        self.xyz_mode = None
        self.buttons = []
        self.xyz_groups = None
        self.controls = []
        self.copy_status = ""
        self.flow_evidence = None
        self.switch_xyz(group)
        if not 0 <= index < len(review.pairs) and not (index == 0 and not review.pairs):
            raise ValueError(f"Pair index must be between 1 and {len(review.pairs)}")
        self.index = index

    def visible_landmarks(self, pair):
        if "_offset" in pair:
            full = self.review.pair_store.load(pair)
            features = full["stereo"]["feature_results"]
            return [features[int(i)] for i in pair["_selected_features"]]
        if "viewer_features" in pair:
            return pair["viewer_features"]
        if "feature_results" in pair.get("stereo", {}):
            return pair["stereo"]["feature_results"]
        saved = pair.get("stereo", {}).get("landmarks", [])
        matches = pair.get("feature_matches", [])
        if "ransac" not in pair:
            return saved or matches
        # The evaluator saves feature_matches after RANSAC, never its rejected set.
        xyz = {(p["query_feature_id"], p["historical_feature_id"]): p for p in saved}
        rejected = {tuple(ids) for ids in pair["ransac"].get("rejected_feature_pairs", [])}
        return [
            {**p, **xyz.get((p["query_feature_id"], p["historical_feature_id"]), {})}
            for p in matches
            if (p["query_feature_id"], p["historical_feature_id"]) not in rejected
        ]

    def prepare_xyz_groups(self):
        if self.xyz_groups is None:
            if self.feature_mode:
                self.xyz_groups = {
                    mode: [] for mode in ("all", "supported", "contradicted", "untestable")
                }
                self.feature_group_counts = {mode: 0 for mode in self.xyz_groups}
                for pair in self.review.all_pairs:
                    if "_feature_verdicts" in pair:
                        verdicts = pair["_feature_verdicts"]
                        for mode, code in (
                            ("all", 0),
                            ("supported", 1),
                            ("contradicted", 2),
                            ("untestable", 3),
                        ):
                            indices = (
                                np.arange(len(verdicts), dtype=np.int32)
                                if mode == "all"
                                else np.flatnonzero(verdicts == code).astype(np.int32)
                            )
                            if len(indices):
                                self.xyz_groups[mode].append(
                                    {
                                        **pair,
                                        "_selected_features": indices,
                                        "viewer_xyz_status": "feature evaluation",
                                    }
                                )
                                self.feature_group_counts[mode] += len(indices)
                        continue
                    features = pair.get("stereo", {}).get("feature_results", [])
                    for mode in self.xyz_groups:
                        selected = [f for f in features if mode == "all" or f["verdict"] == mode]
                        if selected:
                            self.xyz_groups[mode].append(
                                {
                                    **pair,
                                    "viewer_features": selected,
                                    "viewer_xyz_status": "feature evaluation",
                                }
                            )
                            self.feature_group_counts[mode] += len(selected)
                return
            height, width = self.review.load_images(self.review.all_pairs[0])[0].shape[:2]
            self.xyz_groups = {"all": [], "supported": [], "not supported": []}
            for pair in self.review.all_pairs:
                status = xyz_pair_status(pair, self.review.policy, width, height)
                enriched = {**pair, "viewer_xyz_status": status}
                self.xyz_groups["all"].append(enriched)
                self.xyz_groups["supported" if status == "supported" else "not supported"].append(
                    enriched
                )

    def switch_xyz(self, mode):
        self.prepare_xyz_groups()
        if self.feature_mode and mode == "not supported":
            mode = "contradicted"
        self.xyz_mode = mode
        self.review.pairs = self.xyz_groups[mode]
        self.index = self.feature = 0
        self._loaded_index, self._images = None, None
        self.image_boxes = []
        self.dirty = True
        self.copy_status = ""

    def draw_buttons(self, canvas):
        self.buttons = [
            (24, 88, 476, 148, "all"),
            (494, 88, 946, 148, "supported"),
            (964, 88, 1416, 148, "not supported"),
        ]
        if self.feature_mode:
            self.buttons = [
                (24 + i * 354, 88, 360 + i * 354, 148, mode)
                for i, mode in enumerate(("all", "supported", "contradicted", "untestable"))
            ]
        for index, (left, top, right, bottom, mode) in enumerate(self.buttons):
            active = self.xyz_mode == mode
            card(canvas, left, top, right, bottom, border=ACCENT if active else BORDER)
            label(
                canvas,
                f"{index + 1}  "
                + (
                    {"all": "All reported matches", "supported": "Supported features"}.get(
                        mode, GROUP_LABELS[mode]
                    )
                    if self.feature_mode
                    else GROUP_LABELS[mode]
                ),
                left + 16,
                top + 25,
                0.55,
                ACCENT if active else MUTED,
            )
            count = f"{self.feature_group_counts[mode] if self.feature_mode else len(self.xyz_groups[mode]):,}"
            label(
                canvas,
                count,
                right - 16 - cv2.getTextSize(count, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 1)[0][0],
                top + 48,
                0.7,
            )

    def move(self, step):
        if self.feature_mode:
            self.select_feature(step)
            return
        if not self.review.pairs:
            return
        self.index = max(0, min(len(self.review.pairs) - 1, self.index + step))
        self.feature = 0
        self.dirty = True
        self.copy_status = ""

    def select_feature(self, step):
        if not self.review.pairs:
            return
        count = len(self.visible_landmarks(self.review.pairs[self.index]))
        if not count:
            return
        if self.feature_mode:
            target = self.feature + step
            if target >= count:
                if self.index + 1 < len(self.review.pairs):
                    self.index += 1
                    self.feature = 0
                else:
                    self.feature = count - 1
            elif target < 0:
                if self.index > 0:
                    self.index -= 1
                    self.feature = len(self.visible_landmarks(self.review.pairs[self.index])) - 1
                else:
                    self.feature = 0
            else:
                self.feature = target
        else:
            self.feature = (self.feature + step) % count
        self.dirty = True
        self.copy_status = ""

    def draw_flow(self, canvas, pair, width, height):
        policy = self.review.policy
        if self.feature_mode:
            return self.draw_feature_flow(canvas, pair)
        saved = pair.get("stereo", {}).get("landmarks", [])
        passing = [
            p
            for p in saved
            if p["mahalanobis_squared"] <= policy["stereo_world_mahalanobis_squared_maximum"]
        ]
        spatial = (
            min(
                coverage(np.array([p[f"{role}_feature_xy"] for p in passing]), width, height)
                for role in ("query", "historical")
            )
            if passing and policy.get("version", 0) < 7
            else 0
        )
        total, depth_required, pass_required = support_counts(pair, policy)
        ratio = len(passing) / total if total else 0.0
        poses = pair.get("pose_evidence", {}).get(
            "available", pair["measurements"].get("reference_pose_available")
        )
        status = pair["viewer_xyz_status"]
        good, warn, bad = ACCENT, (95, 190, 240), (95, 95, 235)
        enough = total > 0 and len(saved) >= depth_required
        triangulated = pair.get("stereo", {}).get("paired_landmarks", len(saved))
        agree = (
            enough
            and len(passing) >= pass_required
            and ratio >= policy["minimum_inlier_ratio"]
            and (policy.get("version", 0) >= 7 or spatial >= policy["minimum_image_coverage"])
        )
        pose = pair.get("pose_evidence", {})
        trace = self.review.retrieval.get(pair["query_timestamp_ns"], {})
        candidate = next(
            (
                c
                for c in trace.get("candidates", [])
                if c["historical_timestamp_ns"] == pair["historical_timestamp_ns"]
            ),
            {},
        )
        score = candidate.get("score")
        time_q, time_h = (
            pose.get("query_pose_time_error_ns"),
            pose.get("historical_pose_time_error_ns"),
        )
        q_ms, h_ms = (value / 1e6 if value is not None else None for value in (time_q, time_h))
        stages = [
            (
                "01  RETRIEVAL",
                "Candidate returned",
                good,
                [
                    f"Rank {pair['rank']} / "
                    + ("cosine score " if "descriptor_dimension" in trace else "BoW score ")
                    + number(score, 6),
                    f"History searched: {trace.get('eligible_history_count', 'N/A')}",
                    f"Features: {trace.get('feature_count', 'N/A')}",
                    f"Descriptor dimensions: {trace['descriptor_dimension']}"
                    if "descriptor_dimension" in trace
                    else f"BoW words: {trace.get('bow_word_count', 'N/A')}",
                    f"Retrieval: {number(trace.get('timings_ms', {}).get('retrieval'), 3)} ms",
                ],
            ),
            (
                "02  REFERENCE POSES",
                "Available" if poses else "Unavailable" if poses is False else "Not recorded",
                good if poses else warn,
                [
                    f"Timestamp gate: <= {policy['pose_timestamp_tolerance_ms']} ms",
                    f"Current / past dt: {number(q_ms, 2)} / {number(h_ms, 2)} ms",
                    "P_world = T_WB * T_BC * P_cam",
                    f"Position sigma: {policy['reference_position_sigma_m']} m (assumed)",
                    f"Rotation sigma: {policy['reference_orientation_sigma_degrees']} deg (assumed)",
                ],
            ),
            (
                "03  STEREO LANDMARKS",
                f"{triangulated} depths / {len(saved)} world XYZ",
                good if triangulated >= depth_required and total > 0 else warn,
                [
                    f"Depth range: {policy['stereo_minimum_depth_m']} - {policy['stereo_maximum_depth_m']} m",
                    f"Parallax gate: >= {policy['stereo_minimum_parallax_degrees']} deg",
                    f"Stereo pixel error: <= {policy['stereo_maximum_reprojection_px']} px",
                    f"Depth sigma / depth: <= {policy['stereo_maximum_relative_depth_sigma']}",
                    (
                        f"Stereo: FFS / LR <= {policy['stereo_lr_max_error_px']} px"
                        if policy.get("stereo_backend") == "fast_foundationstereo"
                        else f"Pixel noise sigma: {policy['stereo_pixel_sigma_px']} px"
                    ),
                ],
            ),
            (
                "04  XYZ AGREEMENT",
                f"{len(passing)}/{total} matches pass",
                good if agree else bad if status == "rejected" else warn,
                [
                    "M^2 = deltaP^T * C^-1 * deltaP",
                    f"XYZ gate: M^2 <= {policy['stereo_world_mahalanobis_squared_maximum']}",
                    f"Passing / reported: {ratio:.1%}",
                    f"Passing coverage: {spatial:.1%}" if saved else "Passing coverage: N/A",
                    f"Depth available: {len(saved)}/{total} matches",
                ],
            ),
            (
                "05  PAIR DECISION",
                status.title(),
                good if status == "supported" else bad if status == "rejected" else warn,
                [
                    f"Need {pass_required} of {total} matches",
                    f"Support ratio: >= {policy['minimum_inlier_ratio']:.0%}",
                    f"Support coverage: >= {policy.get('minimum_image_coverage', 0):.0%}",
                    f"Reject ratio: <= {policy['contradiction_maximum_inlier_ratio']:.0%}",
                    f"Reject paired coverage: >= {policy.get('minimum_image_coverage', 0):.0%}",
                ],
            ),
        ]
        if policy.get("version", 0) >= 7:
            stages = [
                (
                    title,
                    detail,
                    color,
                    [value for value in technical if "coverage" not in value.lower()],
                )
                for title, detail, color, technical in stages
            ]
            stages[-1][3].append("Decision uses count + XYZ ratio")
        if "ransac" in pair and pair["ransac"]["status"] != "disabled_feature_evaluation":
            r = pair["ransac"]
            stages.insert(
                1,
                (
                    "02  TEMPORAL RANSAC",
                    r["status"].replace("_", " ").title(),
                    good if r["status"] == "fitted" else warn,
                    [
                        f"Raw ORB matches: {r['raw_match_count']}",
                        f"To XYZ: {r['retained_match_count']} / dropped: {r['rejected_match_count']}",
                        f"MAGSAC F / gate: {r['threshold_px']} px",
                        f"Min fit: 8 / seed: {r['seed']}",
                        "Fit uses images only (no GT)",
                    ],
                ),
            )
            stages = [
                (f"{i + 1:02d}  {title.split('  ', 1)[1]}", detail, color, technical)
                for i, (title, detail, color, technical) in enumerate(stages)
            ]
        stride = 1410 // len(stages)
        card_width = stride - 18
        label(canvas, "XYZ EVALUATION FLOW", 24, 651, 0.48, MUTED)
        label(
            canvas,
            "Saved run thresholds / pose noise is assumed / reprojection does not affect the XYZ pair decision",
            480,
            651,
            0.38,
            MUTED,
            936,
        )
        for i, (title, detail, color, technical) in enumerate(stages):
            x = 24 + i * stride
            card(canvas, x, 665, x + card_width, 844, border=color)
            label(canvas, title, x + 14, 688, 0.39, MUTED)
            label(canvas, detail, x + 14, 715, 0.43, color, card_width - 28)
            for row, value in enumerate(technical):
                label(canvas, value, x + 14, 740 + row * 21, 0.34, TEXT, card_width - 28)
            if i < len(stages) - 1:
                cv2.arrowedLine(
                    canvas,
                    (x + card_width + 4, 756),
                    (x + stride - 3, 756),
                    MUTED,
                    1,
                    tipLength=0.4,
                )
        if poses is False:
            reason = "No support: ground-truth poses are missing or outside the timestamp tolerance. 2D matches are not XYZ-tested."
        elif not enough:
            reason = f"Insufficient depth: {len(saved)}/{total} reported matches have world XYZ; need {depth_required} ({policy['minimum_inlier_ratio']:.0%})."
        elif status == "supported":
            reason = f"Supported: {len(passing)}/{total} matches agree in world XYZ ({ratio:.1%}); need {pass_required}."
        elif status == "rejected":
            depth_ratio = len(passing) / len(saved) if saved else 0
            reason = f"Rejected: depth-valid XYZ agreement is {depth_ratio:.0%}, below the {policy['contradiction_maximum_inlier_ratio']:.0%} contradiction limit, with enough evidence."
        else:
            deficits = []
            if len(passing) < pass_required:
                deficits.append(f"{len(passing)}/{total} passing matches; need {pass_required}")
            if ratio < policy["minimum_inlier_ratio"]:
                deficits.append(f"{ratio:.0%} agreement < {policy['minimum_inlier_ratio']:.0%}")
            if policy.get("version", 0) < 7 and spatial < policy["minimum_image_coverage"]:
                deficits.append(
                    f"{spatial:.0%} coverage < {policy.get('minimum_image_coverage', 0):.0%}"
                )
            reason = "Ambiguous: " + "; ".join(deficits) + ". Not enough contradiction to reject."
        label(canvas, reason, 24, 870, 0.46, TEXT, 1392)
        self.flow_evidence = {
            "components": [
                {"component": title, "result": detail, "technical": technical}
                for title, detail, _, technical in stages
            ],
            "reason": reason,
        }

    def draw_feature_flow(self, canvas, pair):
        points = self.visible_landmarks(pair)
        point = points[self.feature]
        color = COLORS[
            {"supported": "passed", "contradicted": "both_failed", "untestable": "not_evaluated"}[
                point["verdict"]
            ]
        ]
        stages = [
            (
                "01  CORRESPONDENCE",
                "Reported feature pair",
                [
                    f"Query ID: {point['query_feature_id']}",
                    f"History ID: {point['historical_feature_id']}",
                    f"Match score: {point['matcher_score']:.4f}"
                    if "matcher_score" in point
                    else f"Hamming: {point['hamming_distance']:.1f}",
                    "All reported matches evaluated",
                    "No temporal RANSAC filtering",
                ],
            ),
            (
                "02  QUERY STEREO",
                "Reliable" if point.get("query_depth_reason") is None else "Untestable",
                stereo_details(point, pair, "query", self.review.policy),
            ),
            (
                "03  HISTORY STEREO",
                "Reliable" if point.get("historical_depth_reason") is None else "Untestable",
                stereo_details(point, pair, "historical", self.review.policy),
            ),
            (
                "04  WORLD XYZ",
                "Compared" if "mahalanobis_squared" in point else "Unavailable",
                [
                    "P_world = T_WCam * P_cam",
                    "Reference camera poses",
                    f"XYZ distance: {number(point.get('xyz_error_m'))} m",
                    f"M^2: {number(point.get('mahalanobis_squared'))}",
                ],
            ),
            (
                "05  FEATURE VERDICT",
                point["verdict"].title(),
                [
                    f"XYZ gate: <= {self.review.policy['stereo_world_mahalanobis_squared_maximum']}",
                    "Reprojection is diagnostic",
                    f"XYZ check: {point['xyz_check_ms']:.3f} ms",
                    "No image-wide voting gates",
                ],
            ),
            (
                "06  IMAGE PAIR COUNTS",
                f"{pair['stereo']['reported_correspondences']} reported",
                [
                    f"Supported: {pair['stereo']['feature_counts']['supported']}",
                    f"Contradicted: {pair['stereo']['feature_counts']['contradicted']}",
                    f"Untestable: {pair['stereo']['feature_counts']['untestable']}",
                    "Counts are feature observations",
                ],
            ),
        ]
        label(canvas, "FEATURE XYZ EVALUATION FLOW", 24, 651, 0.48, MUTED)
        for i, (title, detail, technical) in enumerate(stages):
            x = 24 + i * 235
            card(canvas, x, 665, x + 217, 844, border=color if i == 4 else BORDER)
            label(canvas, title, x + 14, 688, 0.34, MUTED, 190)
            label(canvas, detail, x + 14, 715, 0.43, color, 190)
            for row, value in enumerate(technical):
                label(canvas, value, x + 14, 740 + row * 21, 0.33, TEXT, 190)
        reason = f"{point['verdict'].title()}: {point['reason'].replace('_', ' ')}."
        if point["verdict"] == "untestable":
            reason += f" Query: {point.get('query_depth_reason') or 'available'}; history: {point.get('historical_depth_reason') or 'available'}."
        label(canvas, reason, 24, 870, 0.45, TEXT, 1392)
        self.flow_evidence = {
            "components": [{"component": t, "result": d, "technical": v} for t, d, v in stages],
            "reason": reason,
        }

    def report_text(self):
        if not self.review.pairs:
            raise ValueError("Select a candidate before copying its flow")
        self.render()  # Ensure evidence and feature selection describe the current pair.
        pair = self.review.pairs[self.index]
        if "_offset" in pair:
            pair = {
                **self.review.pair_store.load(pair),
                "viewer_features": self.visible_landmarks(pair),
                "viewer_xyz_status": pair["viewer_xyz_status"],
            }
        points = self.visible_landmarks(pair)
        selected = points[self.feature] if points else None
        fallback = not selected or "mahalanobis_squared" not in selected
        lines = [
            "# LDO candidate review",
            "",
            "## Reviewer observation",
            "I believe this pair should be XYZ-supported because: [add your observation]",
            "",
            "## Pair",
            f"- Evidence directory: {self.review.checks}",
            f"- Group: {GROUP_LABELS[self.xyz_mode]}; pair {self.index + 1} of {len(self.review.pairs)}",
            f"- Current timestamp (ns): {pair['query_timestamp_ns']}",
            f"- Historical timestamp (ns): {pair['historical_timestamp_ns']}",
            f"- {getattr(self.review, 'detector_label', 'ORB + DBoW2')} retrieval rank: {pair['rank']}",
            f"- XYZ-only decision: {selected['verdict'] if self.feature_mode and selected else pair['viewer_xyz_status']}",
            (
                f"- Feature reason: {selected['reason']}"
                if self.feature_mode and selected
                else f"- Saved combined checker decision: {pair['outcome']}"
            ),
            "",
            "## Component flow",
        ]
        for component in self.flow_evidence["components"]:
            lines.extend(
                [
                    "",
                    f"### {component['component']}: {component['result']}",
                    *[f"- {value}" for value in component["technical"]],
                ]
            )
        lines.extend(
            [
                "",
                "## Decision explanation",
                self.flow_evidence["reason"],
                "",
                "## Selected feature",
                f"- Selected match: {self.feature + 1 if selected else 'none'} / {len(points)}",
                f"- Source: {getattr(self.review, 'feature_source', 'Exported upstream ORB')}",
                "- Correspondences are the saved detector assignments; the existing stereo + XYZ checker evaluates them.",
                "```json",
                json.dumps(
                    {
                        "gate": (
                            selected["verdict"]
                            if self.feature_mode
                            else (
                                "not_evaluated"
                                if fallback
                                else landmark_gate(selected, self.review.policy)
                            )
                        )
                        if selected
                        else None,
                        "values": selected,
                    },
                    indent=2,
                ),
                "```",
                "",
                "## Saved numerical evidence",
                "```json",
                json.dumps(
                    {
                        "pose_evidence": pair.get("pose_evidence"),
                        "measurements": pair["measurements"],
                        "ransac": pair.get("ransac"),
                        "stereo_summary": {
                            k: v
                            for k, v in pair.get("stereo", {}).items()
                            if (
                                k
                                in {
                                    "feature_counts",
                                    "reported_correspondences",
                                    "testable_correspondences",
                                    "contradiction_rate",
                                    "evaluation_coverage",
                                    "timings_ms",
                                }
                                if self.feature_mode
                                else k not in {"landmarks", "frames", "feature_results"}
                            )
                        },
                        "xyz_landmarks_passed": sum(
                            p["mahalanobis_squared"]
                            <= self.review.policy["stereo_world_mahalanobis_squared_maximum"]
                            for p in pair.get("stereo", {}).get("landmarks", [])
                        ),
                        "saved_policy": self.review.policy,
                    },
                    indent=2,
                ),
                "```",
            ]
        )
        return "\n".join(lines)

    def copy_flow(self):
        try:
            copy_text(self.report_text())
            self.copy_status = "Copied. Paste into chat."
        except (OSError, RuntimeError, ValueError) as error:
            self.copy_status = "Copy failed. See terminal."
            print(f"Clipboard error: {error}", file=sys.stderr, flush=True)
        self.dirty = True

    def draw_inspector(self, canvas, pair, landmarks, fallback):
        card(canvas, 24, 888, 1416, 1008)
        label(canvas, "FEATURE INSPECTOR", 40, 910, 0.4, MUTED)
        if not landmarks:
            label(canvas, "No feature correspondences available for this pair.", 40, 940, 0.56)
            label(
                canvas,
                "Pair counts and decisions use the saved evaluation evidence.",
                40,
                973,
                0.44,
                MUTED,
            )
            return
        point = landmarks[self.feature]
        label(canvas, f"Match {self.feature + 1} / {len(landmarks)}", 40, 939, 0.65)
        q, h = point["query_feature_xy"], point["historical_feature_xy"]
        label(
            canvas,
            f"Pixels  ({q[0]:.1f}, {q[1]:.1f})  ->  ({h[0]:.1f}, {h[1]:.1f})",
            40,
            968,
            0.42,
            MUTED,
        )
        if "mahalanobis_squared" not in point:
            label(
                canvas,
                "2D correspondence / XYZ not evaluated",
                400,
                939,
                0.56,
                COLORS["not_evaluated"],
            )
            label(
                canvas,
                "Saved feature match for visual inspection; no depth or world-position verdict.",
                400,
                968,
                0.44,
                MUTED,
                980,
            )
            return
        gate = (
            {"supported": "passed", "contradicted": "both_failed", "untestable": "not_evaluated"}[
                point["verdict"]
            ]
            if self.feature_mode
            else landmark_gate(point, self.review.policy)
        )
        descriptions = {
            "passed": "XYZ and reprojection pass",
            "xyz_failed": "XYZ fails / reprojection passes",
            "reprojection_failed": "XYZ passes / reprojection fails",
            "both_failed": "XYZ and reprojection fail",
        }
        label(
            canvas,
            point["verdict"].title() if self.feature_mode else descriptions[gate],
            400,
            912,
            0.44,
            COLORS[gate],
        )
        label(canvas, f"XYZ distance  {point['xyz_error_m']:.4f} m", 400, 941, 0.52)
        label(
            canvas,
            f"M^2  {point['mahalanobis_squared']:.3f} / limit {self.review.policy['stereo_world_mahalanobis_squared_maximum']}",
            400,
            969,
            0.42,
            MUTED,
        )
        label(
            canvas,
            f"Largest-axis 3-sigma radius: {point['three_sigma_radius_m']:.3f} m",
            400,
            991,
            0.36,
            MUTED,
        )
        label(
            canvas,
            f"Current world  {vector(point['query_world_xyz'])} m",
            750,
            912,
            0.42,
            TEXT,
            640,
        )
        label(
            canvas,
            f"Past world     {vector(point['historical_world_xyz'])} m",
            750,
            939,
            0.42,
            TEXT,
            640,
        )
        errors = point["cross_reprojection_px"] or [None, None]
        label(
            canvas,
            f"Reprojection  {number(errors[0], 2)} / {number(errors[1], 2)} px   |   limit {self.review.policy['stereo_cross_reprojection_px']} px",
            750,
            967,
            0.42,
            MUTED,
            640,
        )

    def draw_matches(self, canvas, landmarks, gates):
        if not self.overlay:
            return
        for index, (point, gate) in enumerate(zip(landmarks, gates, strict=True)):
            locations = []
            for side, role in enumerate(("query", "historical")):
                x, y, scale, _, _ = self.image_boxes[side]
                pixel = point[f"{role}_feature_xy"]
                locations.append((round(x + pixel[0] * scale), round(y + pixel[1] * scale)))
            selected = index == self.feature
            if self.all_lines or selected:
                cv2.line(
                    canvas,
                    locations[0],
                    locations[1],
                    COLORS[gate],
                    2 if selected else 1,
                    cv2.LINE_AA,
                )
            for location in locations:
                cv2.circle(canvas, location, 3, COLORS[gate], 1, cv2.LINE_AA)
                if self.ids or selected:
                    label(
                        canvas, str(index + 1), location[0] + 6, location[1] - 6, 0.32, COLORS[gate]
                    )
                if selected:
                    cv2.circle(canvas, location, 9, TEXT, 2, cv2.LINE_AA)

    def render(self):
        canvas = np.full((CANVAS_HEIGHT, CANVAS_WIDTH, 3), BACKGROUND, np.uint8)
        label(canvas, "LDO", 24, 41, 0.95)
        label(canvas, "CANDIDATE REVIEW", 108, 39, 0.52, MUTED)
        detector_label = getattr(self.review, "detector_label", "ORB + DBoW2")
        label(canvas, f"{detector_label} / stereo / XYZ", 24, 66, 0.44, MUTED, 610)
        label(
            canvas,
            f"GT-eligible {len(self.review.all_pairs):,} / excluded {self.review.excluded_count:,}",
            1000,
            39,
            0.4,
            MUTED,
            416,
        )
        if not self.feature_mode:
            cv2.circle(canvas, (650, 62), 3, COLORS["not_evaluated"], -1)
            label(canvas, "2D only", 660, 66, 0.35, MUTED)
        if self.feature_mode:
            label(
                canvas,
                "Colors: green = supported / red = contradicted / cyan = untestable",
                650,
                66,
                0.36,
                MUTED,
                760,
            )
        for x, name, gate in (
            []
            if self.feature_mode
            else [
                (820, "Both pass", "passed"),
                (960, "Pixel fail", "reprojection_failed"),
                (1100, "XYZ fail", "xyz_failed"),
                (1240, "Both fail", "both_failed"),
            ]
        ):
            cv2.circle(canvas, (x, 62), 3, COLORS[gate], -1)
            label(canvas, name, x + 10, 66, 0.35, MUTED)
        self.draw_buttons(canvas)
        self.controls = []
        if not self.review.pairs:
            label(canvas, "No candidates in this group", 460, 410, 0.85)
            label(canvas, "Choose another tab to continue.", 525, 450, 0.5, MUTED)
            self.image_boxes = []
            return canvas
        pair = self.review.pairs[self.index]
        if "_offset" in pair:
            pair = {
                **self.review.pair_store.load(pair),
                "viewer_features": self.visible_landmarks(pair),
                "viewer_xyz_status": pair["viewer_xyz_status"],
            }
        if self._loaded_index != self.index:
            self._images = self.review.load_images(pair)
            self._loaded_index = self.index
        landmarks = self.visible_landmarks(pair)
        fallback = not pair.get("stereo", {}).get("landmarks")
        gates = [
            {"supported": "passed", "contradicted": "both_failed", "untestable": "not_evaluated"}[
                p["verdict"]
            ]
            if self.feature_mode
            else (
                "not_evaluated"
                if "mahalanobis_squared" not in p
                else landmark_gate(p, self.review.policy)
            )
            for p in landmarks
        ]
        status = (
            landmarks[self.feature]["verdict"] if self.feature_mode else pair["viewer_xyz_status"]
        )
        pose = pair.get("pose_evidence", {})
        gap = (pair["query_timestamp_ns"] - pair["historical_timestamp_ns"]) / 1e9
        label(
            canvas,
            f"PAIR {self.index + 1:,} / {len(self.review.pairs):,}   |   "
            + (f"Feature {self.feature + 1}/{len(landmarks)}   |   " if self.feature_mode else "")
            + f"Rank {pair['rank']} / {gap:.1f}s",
            24,
            176,
            0.46,
            TEXT,
            650,
        )
        label(
            canvas,
            f"XYZ: {status}",
            700,
            176,
            0.48,
            ACCENT if status == "supported" else (95, 190, 240),
            425,
        )
        self.image_boxes = []
        for side, (image, role) in enumerate(
            zip(self._images, ("query", "historical"), strict=True)
        ):
            left = 24 + side * 708
            card(canvas, left, 193, left + 684, 616)
            name = "CURRENT FRAME" if side == 0 else "HISTORICAL CANDIDATE"
            label(canvas, name, left + 12, 214, 0.4, MUTED)
            label(canvas, str(pair[f"{role}_timestamp_ns"]) + " ns", left + 350, 214, 0.38, MUTED)
            scale = min(684 / image.shape[1], 390 / image.shape[0])
            w, h = round(image.shape[1] * scale), round(image.shape[0] * scale)
            x, y = left + (684 - w) // 2, 225 + (390 - h) // 2
            paste_image(canvas, cv2.resize(image, (w, h)), x, y)
            self.image_boxes.append((x, y, scale, w, h))
        self.draw_matches(canvas, landmarks, gates)
        label(
            canvas,
            f"{len(landmarks)} marks  |  {detector_label} / saved feature assignments / calibrated stereo XYZ",
            24,
            635,
            0.4,
            MUTED,
            880,
        )
        label(
            canvas,
            f"Camera distance {number(pose.get('camera_position_distance_m'), 2)} m  /  angle {number(pose.get('camera_orientation_difference_degrees'), 1)} deg",
            930,
            635,
            0.4,
            MUTED,
            486,
        )
        height, width = self._images[0].shape[:2]
        self.draw_flow(canvas, pair, width, height)
        self.draw_inspector(canvas, pair, landmarks, fallback)
        # Direct controls share the same behavior as the keyboard shortcuts.
        controls = [
            (1140, 157, 1268, 184, "prev", "< Previous"),
            (1280, 157, 1416, 184, "next", "Next >"),
            (1240, 1017, 1416, 1044, "copy", "Copy flow  [C]"),
        ]
        # Navigation stays in the top-right strip; decision label sits below tabs.
        for left, top, right, bottom, action, title in controls:
            card(canvas, left, top, right, bottom)
            label(canvas, title, left + 10, top + 19, 0.43)
            self.controls.append((left, top, right, bottom, action))
        label(
            canvas,
            (
                "1/2/3/4: features   A/D or [ ]: previous/next feature   L: all lines   C: copy   Q: quit"
                if self.feature_mode
                else "1/2/3: tabs   A/D: pairs   [ ]: match   Click: inspect   L: lines   I: IDs   V: marks   Q: quit"
            ),
            24,
            1034,
            0.43,
            MUTED,
            930,
        )
        label(canvas, self.copy_status, 990, 1034, 0.38, ACCENT, 236)
        return canvas

    def mouse(self, event, x, y, flags, parameter):
        if event != cv2.EVENT_LBUTTONDOWN:
            return
        for left, top, right, bottom, mode in self.buttons:
            if left <= x <= right and top <= y <= bottom:
                self.switch_xyz(mode)
                return
        for left, top, right, bottom, action in self.controls:
            if left <= x <= right and top <= y <= bottom:
                if action == "copy":
                    self.copy_flow()
                else:
                    self.move(-1 if action == "prev" else 1)
                return
        if not self.review.pairs:
            return
        landmarks = self.visible_landmarks(self.review.pairs[self.index])
        if not landmarks:
            return
        for side, (left, top, scale, width, height) in enumerate(self.image_boxes):
            if left <= x < left + width and top <= y < top + height:
                role = ("query", "historical")[side]
                points = np.array([point[f"{role}_feature_xy"] for point in landmarks]) * scale + [
                    left,
                    top,
                ]
                distances = np.linalg.norm(points - [x, y], axis=1)
                index = int(np.argmin(distances))
                if distances[index] <= 15:
                    self.feature, self.dirty = index, True
                    self.copy_status = ""
                return

    def run(self, smoke_test=False):
        try:
            cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(WINDOW, 1440, 1000)
            cv2.setMouseCallback(WINDOW, self.mouse)
            if smoke_test:
                cv2.imshow(WINDOW, self.render())
                cv2.waitKey(300)
                return
            while True:
                if self.dirty:
                    cv2.imshow(WINDOW, self.render())
                    self.dirty = False
                key = cv2.waitKeyEx(50)
                if key in (27, ord("q"), ord("Q")):
                    break
                if key in (2555904, 65363, 63235, ord("d"), ord("D")):
                    self.move(1)
                elif key in (2424832, 65361, 63234, ord("a"), ord("A")):
                    self.move(-1)
                elif key == ord("]"):
                    self.select_feature(1)
                elif key == ord("["):
                    self.select_feature(-1)
                elif key == ord("1"):
                    self.switch_xyz("all")
                elif key == ord("2"):
                    self.switch_xyz("supported")
                elif key == ord("3"):
                    self.switch_xyz("contradicted" if self.feature_mode else "not supported")
                elif key == ord("4") and self.feature_mode:
                    self.switch_xyz("untestable")
                elif key in (ord("l"), ord("L")):
                    self.all_lines, self.dirty = not self.all_lines, True
                elif key in (ord("v"), ord("V")):
                    self.overlay, self.dirty = not self.overlay, True
                elif key in (ord("i"), ord("I")):
                    self.ids, self.dirty = not self.ids, True
                elif key in (ord("c"), ord("C")):
                    self.copy_flow()
                elif key in (ord("r"), ord("R")):
                    self.index, self.feature, self.dirty = 0, 0, True
                try:
                    if cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                        break
                except cv2.error:
                    break  # Some GUI backends destroy the window before the query.
        except cv2.error as error:
            raise RuntimeError(
                "OpenCV GUI unavailable. On Windows run: uv sync; uv run python evaluation/view_suspicious.py. Use --export for a headless preview."
            ) from error
        finally:
            try:
                cv2.destroyAllWindows()
            except cv2.error:
                pass


def main():
    parser = argparse.ArgumentParser(
        description="Review ORB + DBoW2 candidates and independent XYZ evidence"
    )
    parser.add_argument(
        "--checks", type=Path, help="candidate_checks directory; default latest completed report"
    )
    parser.add_argument("--dataset-root", type=Path, default=PROJECT / "evaluation/datasets/euroc")
    parser.add_argument(
        "--pair", type=int, default=1, help="Initial pair in selected group, starting at 1"
    )
    parser.add_argument("--export", type=Path, help="Save preview PNG without opening a GUI")
    parser.add_argument(
        "--smoke-test", action="store_true", help="Open and close the GUI for verification"
    )
    parser.add_argument(
        "--group",
        choices=("all", "supported", "not supported", "contradicted", "untestable"),
        default="all",
        help="Initial candidate review button",
    )
    args = parser.parse_args()
    try:
        review = EvidenceReview(args.checks or latest_checks(), args.dataset_root)
        viewer = PairViewer(review, args.pair - 1, args.group)
        print(
            f"Feature groups: {viewer.feature_group_counts}"
            if viewer.feature_mode
            else f"Candidate groups: { {mode: len(pairs) for mode, pairs in viewer.xyz_groups.items()} }",
            flush=True,
        )
        if args.export:
            args.export.parent.mkdir(parents=True, exist_ok=True)
            if not cv2.imwrite(str(args.export), viewer.render()):
                raise RuntimeError(f"Cannot write preview: {args.export}")
            print(f"Preview: {args.export}")
        else:
            viewer.run(args.smoke_test)
        return 0
    except (ValueError, OSError, RuntimeError) as error:
        parser.exit(1, f"Viewer error: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
