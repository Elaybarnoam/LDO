"""Distance, surface ambiguity and known wrong matches exercise actual verdicts."""

import gzip
import json
from pathlib import Path

import cv2
import numpy as np
import pytest
import yaml
from tasks.loop_closure.comparison.reference import sha256, write_json
from tasks.reference_depth_v2.geometry import check_features, sample_surface
from tasks.reference_depth_v2.workflow import rescore_sequence

POLICY = yaml.safe_load(
    (
        Path(__file__).resolve().parents[1] / "evaluation/src/tasks/reference_depth_v2/config.yaml"
    ).read_text()
)


def check(q, h, z, other=None, relative=None, semantics=None):
    depth = np.full((640, 640), z, np.float32)
    sem = np.ones(depth.shape, np.uint8) if semantics is None else semantics
    return check_features(
        q,
        h,
        depth,
        depth if other is None else other,
        sem,
        sem,
        np.eye(4) if relative is None else relative,
        {1, 2},
        2,
        POLICY,
    )


@pytest.mark.parametrize("distance", [0.1, 4.0, 100.0, 10000.0])
def test_near_and_far_correct_and_displaced_matches(distance):
    result = check([[320, 320], [320, 320]], [[320, 320], [330, 320]], distance)
    assert result["verdicts"].tolist() == ["supported", "contradicted"]


def test_nonidentity_camera_pose_and_wrong_depth():
    relative = np.eye(4)
    relative[0, 3] = 1
    assert (
        check([[320, 320]], [[323.2, 320]], 100.0, relative=relative)["verdicts"][0] == "supported"
    )
    assert (
        check([[320, 320]], [[320, 320]], 100.0, other=np.full((640, 640), 120.0))["verdicts"][0]
        == "contradicted"
    )


def test_active_footprint_ignores_unrelated_neighbour_but_not_boundary():
    depth = np.full((640, 640), 4.0)
    sem = np.ones(depth.shape, np.uint8)
    depth[319, 319] = 100.0
    z, valid, _ = sample_surface(depth, sem, [[320.2, 320.2]], {1, 2}, 2, POLICY)
    assert valid[0] and z[0] == pytest.approx(4.0)
    depth[320, 321] = 100.0
    _, valid, reasons = sample_surface(depth, sem, [[320, 320], [320.2, 320.2]], {1, 2}, 2, POLICY)
    assert valid.tolist() == [True, False]
    assert reasons[1] == "ambiguous_depth_boundary"


def test_inverse_depth_interpolation_is_exact_on_slanted_plane():
    x, y = np.meshgrid(np.arange(640), np.arange(640))
    depth = 1 / (0.2 + x * 0.00001 + y * 0.00002)
    p = np.array([[320.2, 310.7]])
    z, valid, _ = sample_surface(depth, np.ones(depth.shape), p, {1, 2}, 2, POLICY)
    assert valid[0]
    assert z[0] == pytest.approx(1 / (0.2 + p[0, 0] * 0.00001 + p[0, 1] * 0.00002))


def test_sky_unmapped_invalid_and_border_pixels():
    depth = np.full((640, 640), 10000.0)
    sem = np.ones(depth.shape, np.uint8)
    sem[320, 320], sem[321, 321] = 2, 0
    depth[322, 322] = np.nan
    p = [[320, 320], [321, 321], [322, 322], [-1, 5], [np.nan, 5], [0, 0], [639, 639]]
    _, valid, reasons = sample_surface(depth, sem, p, {1, 2}, 2, POLICY)
    assert valid.tolist() == [False] * 5 + [True, True]
    assert reasons[:3].tolist() == ["sky", "unmapped_semantics", "nonpositive_or_nonfinite_depth"]


def test_match_on_sky_is_unknown_not_correct():
    sem = np.full((640, 640), 2, np.uint8)
    assert check([[320, 320]], [[320, 320]], 10000.0, semantics=sem)["verdicts"][0] == "untestable"


def test_saved_evidence_replay_preserves_ids_and_checks_hashes(tmp_path):
    replay = tmp_path / "replay"
    replay.mkdir()
    source = tmp_path / "SceneA/Data_easy/P000/depth_lcam_front"
    source.mkdir(parents=True)
    depth = source / "000000_lcam_front_depth.png"
    z = np.full((640, 640), 100.0, np.float32)
    cv2.imwrite(str(depth), z.view(np.uint8).reshape(640, 640, 4))
    image = replay / "image.png"
    cv2.imwrite(str(image), np.zeros((640, 640), np.uint8))
    frames = [
        {
            "timestamp_ns": stamp,
            "source_index": 0,
            "depth": str(depth),
            "image": str(image),
            "depth_sha256": sha256(depth),
            "image_sha256": sha256(image),
            "pose": np.eye(4).tolist(),
        }
        for stamp in (1, 2)
    ]
    write_json(replay / "frames.json", frames)
    write_json(replay / "events.json", [])
    (replay / "reference.jsonl").write_text("")
    reference = {
        "root": str(replay),
        **{
            key: sha256(replay / name)
            for key, name in (
                ("frames_sha256", "frames.json"),
                ("events_sha256", "events.json"),
                ("reference_sha256", "reference.jsonl"),
            )
        },
    }
    assets = tmp_path / "assets"
    semantic = assets / "SceneA/Data_easy/P000/seg_lcam_front"
    semantic.mkdir(parents=True)
    cv2.imwrite(str(semantic / "000000_lcam_front_seg.png"), np.ones((640, 640), np.uint8))
    write_json(assets / "seg_label_map.json", {"name_map": {"wall": 1, "sky": 2}})
    evidence = tmp_path / "evidence/P000"
    evidence.mkdir(parents=True)
    original = [
        {
            "method": method,
            "query_timestamp_ns": 2,
            "historical_timestamp_ns": 1,
            "query_feature_id": 7,
            "historical_feature_id": 8,
            "query_pixel": [320.0, 320.0],
            "historical_pixel": [320.0 if correct else 330.0, 320.0],
            "verdict": "untestable",
        }
        for method in ("orb", "ldo")
        for correct in (True, False)
    ]
    path = evidence / "feature_checks.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in original))
    sequence = {
        "trajectory": "P000",
        "reference": reference,
        "feature_evidence_root": str(evidence.parent),
        "artifact_hashes": {"feature_checks": sha256(path)},
        "features": {
            m: {"supported": 0, "contradicted": 0, "untestable": 2} for m in ("orb", "ldo")
        },
    }
    asset = {
        "root": str(assets),
        "environment": "SceneA",
        "labels_sha256": sha256(assets / "seg_label_map.json"),
    }
    output = tmp_path / "output"
    output.mkdir()
    result = rescore_sequence(sequence, asset, POLICY, output)
    for stats in result["methods"].values():
        assert stats["new"] == {"supported": 1, "contradicted": 1, "untestable": 0}
        assert stats["transitions"] == {"untestable->supported": 1, "untestable->contradicted": 1}
    with gzip.open(result["evidence"], "rt") as stream:
        saved = [json.loads(line) for line in stream]
    assert len(saved) == len(original)
    assert all(r["query_feature_id"] == 7 and r["historical_feature_id"] == 8 for r in saved)
    path.write_text("changed")
    with pytest.raises(ValueError, match="assignments changed"):
        rescore_sequence(sequence, asset, POLICY, output)
