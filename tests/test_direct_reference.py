"""Direct evaluation must measure assignments without operational selection."""

import json
from pathlib import Path

import cv2
import numpy as np
import pytest
import yaml
from tasks.loop_closure.comparison.reference import sha256, write_json
from tasks.loop_closure.revisits.metrics import build_events
from tasks.reference_geometry import direct
from tasks.reference_geometry.direct_report import aggregate, render

ROOT = Path(__file__).resolve().parents[1]
POLICY = yaml.safe_load((ROOT / "evaluation/src/tasks/reference_geometry/config.yaml").read_text())[
    "protocol"
]


def test_feature_world_coordinates_explain_match_verdicts():
    depth = np.full((640, 640), 4.0, np.float32)
    qpose = np.eye(4)
    qpose[:3, 3] = [2, 3, 4]
    hpose = qpose.copy()
    pixels = np.array([[320.0, 320.0], [100.0, 100.0], [0.0, 0.0]])
    historical = np.array([[320.0, 320.0], [400.0, 400.0], [0.0, 0.0]])
    ids = np.column_stack([np.arange(3), np.arange(3)])
    counts, records = direct.feature_records(
        "ldo",
        6_000_000_000,
        1_000_000_000,
        ids,
        pixels,
        historical,
        depth,
        depth,
        qpose,
        hpose,
        POLICY,
    )
    assert counts == {"supported": 1, "contradicted": 1, "untestable": 1}
    assert records[0]["query_world_xyz_m"][2] == 8
    for record in records[:2]:
        distance = np.linalg.norm(
            np.array(record["query_world_xyz_m"]) - record["historical_world_xyz_m"]
        )
        assert distance == pytest.approx(record["xyz_error_m"])
    assert records[2]["query_world_xyz_m"] is None
    assert records[2]["xyz_error_m"] is None


@pytest.fixture
def saved_evidence(tmp_path, monkeypatch):
    config = yaml.safe_load(
        (ROOT / "evaluation/src/tasks/reference_geometry/config.yaml").read_text()
    )
    config["dataset"]["trajectories"] = ["P000"]
    config["output"] = str(tmp_path / "outputs")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(config))
    replay = tmp_path / "replay"
    replay.mkdir()
    image = replay / "image.png"
    depth = replay / "depth.png"
    cv2.imwrite(str(image), np.zeros((640, 640), np.uint8))
    z = np.full((640, 640), 4.0, np.float32)
    cv2.imwrite(str(depth), z.view(np.uint8).reshape(640, 640, 4))
    queries = [1_000_000_000, 6_000_000_000]
    frames = [
        {
            "timestamp_ns": q,
            "image": str(image),
            "depth": str(depth),
            "pose": np.eye(4).tolist(),
            "image_sha256": sha256(image),
            "depth_sha256": sha256(depth),
        }
        for q in queries
    ]
    write_json(replay / "frames.json", frames)
    ref = {"query_timestamp_ns": queries[1], "historical_timestamp_ns": queries[0], "label": "loop"}
    (replay / "reference.jsonl").write_text(json.dumps(ref) + "\n")
    write_json(
        replay / "events.json",
        build_events({(queries[1], queries[0]): ref}, queries, POLICY["event_gap_ns"]),
    )
    info = {
        "trajectory": "P000",
        "root": str(replay),
        **{
            key: sha256(replay / name)
            for name, key in (
                ("frames.json", "frames_sha256"),
                ("reference.jsonl", "reference_sha256"),
                ("events.json", "events_sha256"),
            )
        },
    }
    manifest = {
        "dataset": config["dataset"],
        "protocol": config["protocol"],
        "configuration_sha256": sha256(config_path),
        "reference_geometry_code_sha256": sha256(
            ROOT / "evaluation/src/tasks/reference_geometry/geometry.py"
        ),
        "sequences": [info],
    }
    evidence = tmp_path / "evidence"
    hashes = {}
    for method in ("orb", "ldo"):
        path = evidence / "P000" / method / "retrieval.jsonl"
        path.parent.mkdir(parents=True)
        path.write_text(
            "".join(
                json.dumps(
                    {
                        "query_timestamp_ns": q,
                        "eligible_history_count": i,
                        "candidates": []
                        if not i
                        else [{"rank": 1, "historical_timestamp_ns": queries[0], "score": 0.5}],
                    }
                )
                + "\n"
                for i, q in enumerate(queries)
            )
        )
        hashes[f"{method}_trace"] = sha256(path)
    # Previous operational decisions are deliberately unreadable. Direct evaluation
    # must not consult their status, pose, inliers, or selected-feature masks.
    (evidence / "P000/connections.jsonl").write_text("NOT VALID JSON")

    class Features:
        def __init__(self, *args):
            pass

        def features(self, q):
            points = (
                [[320.0, 320.0], [100.0, 100.0], [0.0, 0.0]]
                if q == queries[1]
                else [[320.0, 320.0], [400.0, 400.0], [0.0, 0.0]]
            )
            return np.array(points), None

        def assignments(self, q, h):
            return np.column_stack([np.arange(3), np.arange(3)])

    monkeypatch.setattr(direct, "FeaturePairs", Features)

    def publish(result, root, config_path):
        path = root / "published.json"
        write_json(path, result)
        return path

    monkeypatch.setattr(direct, "publish_report", publish)
    source = {
        "sequence": "fixture",
        "reference_geometry": {
            "manifest": manifest,
            "artifact_directory": str(evidence),
            "sequences": [{"trajectory": "P000", "artifact_hashes": hashes}],
        },
    }
    path = tmp_path / "saved.json"
    write_json(path, source)
    return config, config_path, path, evidence


def test_saved_evaluation_bypasses_verifier_and_checks_every_assignment(
    saved_evidence, monkeypatch
):
    from loop_verification.stereo_depth import StereoDepth
    from loop_verification.verifier import LoopVerifier

    def forbidden(*args, **kwargs):
        pytest.fail("Operational stereo/verifier must not be instantiated")

    monkeypatch.setattr(StereoDepth, "__init__", forbidden)
    monkeypatch.setattr(LoopVerifier, "__init__", forbidden)
    config, path, evidence, _ = saved_evidence
    report = direct.evaluate_saved(config, path, evidence)
    task = json.loads(report.read_text())["reference_geometry"]
    assert task["operational_verifier_used"] is False
    assert task["stereo_estimator_used"] is False
    for method in ("orb", "ldo"):
        stats = task["aggregate"][method]
        assert stats["reported_matches"] == 3
        assert stats["supported"] == stats["contradicted"] == stats["untestable"] == 1
        assert stats["support_among_judgeable"] == 0.5
        assert stats["support_fraction_bounds"] == [1 / 3, 2 / 3]
        assert stats["retrieval"]["detected_confirmed_events"] == 1
    text = "\n".join(render(task))
    assert "Direct reference-depth evaluation" in text
    assert "Accepted constraints" not in text
    assert "pose_consistent" not in task["aggregate"]["ldo"]
    assert "connections" not in task["sequences"][0]


def test_tampered_original_trace_is_rejected(saved_evidence):
    config, path, summary, root = saved_evidence
    (root / "P000/ldo/retrieval.jsonl").write_text("{}")
    with pytest.raises(ValueError, match="trace changed"):
        direct.evaluate_saved(config, path, summary)


def test_partial_detector_evidence_is_rejected(saved_evidence):
    config, path, summary, _ = saved_evidence
    source = json.loads(summary.read_text())
    source["reference_geometry"]["sequences"] = []
    summary.write_text(json.dumps(source))
    with pytest.raises(ValueError, match="every declared trajectory"):
        direct.evaluate_saved(config, path, summary)


def test_empty_matching_denominator_remains_unavailable():
    metrics = {
        "returned_pairs": 1,
        "true_positive_pairs": 0,
        "false_positive_pairs": 1,
        "unknown_pairs": 0,
        "confirmed_events": 0,
        "detected_confirmed_events": 0,
    }
    sequence = {
        "features": {
            m: {"supported": 0, "contradicted": 0, "untestable": 0, "zero_match_pairs": 1}
            for m in ("orb", "ldo")
        },
        "retrieval": {"5": {m: metrics for m in ("orb", "ldo")}},
    }
    row = aggregate([sequence], 5)["ldo"]
    assert row["support_among_judgeable"] is None
    assert row["support_fraction_bounds"] is None
    assert row["zero_match_pairs"] == 1
    assert row["supported_per_returned_pair"] == 0
