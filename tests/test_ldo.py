"""Causal retrieval, adapter invariants and learned evidence integration."""

import json
from pathlib import Path

import cv2
import numpy as np
import pytest
from tasks.feature_matching.xyz.geometry import ImageGeometry
from tasks.feature_matching.xyz.learned_features import SavedCorrespondences
from modules.evaluation_file_handler.markdown_report import _feature_review

from ldo.configuration import load_config
from ldo.contracts import (
    Candidate,
    CorrespondenceBatch,
    KeyframeInput,
    LocalFeatures,
    LoopProposalBatch,
)
from ldo.detector import Detector
from ldo.evidence import EvidenceWriter
from ldo.memory import FeatureCache
from ldo.policies.proposal import RetrievalOrderPolicy
from ldo.retrieval.index import CosineIndex


def features() -> LocalFeatures:
    return LocalFeatures(
        np.array([[20, 30], [40, 50]], np.float32),
        np.eye(2, dtype=np.float32),
        np.ones(2, np.float32),
        (100, 80),
        "fixture",
        "fixture-v1",
    )


class Encoder:
    fingerprint = "encoder-v1"
    dimension = 2

    def encode(self, image: Path):
        return np.array([1, 0], np.float32)

    def close(self):
        pass


class Engine:
    fingerprint = "fixture-v1"

    def extract(self, image: Path):
        return features()

    def match(self, query, history):
        return CorrespondenceBatch(
            np.array([[0, 1]], np.int64), np.array([0.8], np.float32), "fixture_score"
        )

    def close(self):
        pass


def image(tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    assert cv2.imwrite(str(path), np.zeros((80, 100), np.uint8))
    return path


def test_cosine_search_excludes_recent_frames_before_top_k_and_orders_ties(tmp_path):
    index = CosineIndex(2, "v1")
    for stamp, descriptor in ((1, [1, 0]), (2, [1, 0]), (29, [1, 0])):
        index.insert(
            KeyframeInput(str(stamp), stamp, tmp_path / "unused"),
            np.array(descriptor, np.float32),
            "v1",
        )
    count, result = index.query(np.array([1, 0], np.float32), "v1", 30, 20, 5)
    assert count == 2
    assert [frame.timestamp_ns for frame, _ in result] == [1, 2]
    with pytest.raises(ValueError, match="fingerprint"):
        index.query(np.array([1, 0], np.float32), "different_weights", 30, 20, 5)


def test_negative_cosine_is_a_valid_ranked_result(tmp_path):
    index = CosineIndex(2, "v1")
    index.insert(KeyframeInput("past", 1, tmp_path), np.array([-1, 0], np.float32), "v1")
    _, result = index.query(np.array([1, 0], np.float32), "v1", 30, 20, 1)
    assert result[0][1] == -1


def test_detector_queries_before_insert_and_rejects_duplicates_sessions_and_closed_state(tmp_path):
    detector = Detector(Encoder(), Engine(), RetrievalOrderPolicy(), exclusion_ns=20, cache_size=1)
    first = KeyframeInput("one", 1, image(tmp_path, "1.png"))
    assert detector.process_keyframe(first).candidates == ()
    second = KeyframeInput("two", 30, image(tmp_path, "30.png"))
    result = detector.process_keyframe(second)
    assert result.eligible_history_count == 1
    assert result.candidates[0].historical == first
    assert len(result.candidates[0].matches.indices) == 1
    with pytest.raises(ValueError, match="Duplicate"):
        detector.process_keyframe(KeyframeInput("two", 40, second.image_reference))
    with pytest.raises(ValueError, match="sessions"):
        detector.process_keyframe(KeyframeInput("three", 40, second.image_reference, "other"))
    detector.close()
    with pytest.raises(RuntimeError, match="closed"):
        detector.reset()


def test_inference_failure_does_not_insert_partial_history(tmp_path):
    class Failing(Engine):
        def match(self, query, history):
            raise RuntimeError("model failure")

    detector = Detector(Encoder(), Failing(), RetrievalOrderPolicy(), exclusion_ns=1)
    path = image(tmp_path, "image.png")
    detector.process_keyframe(KeyframeInput("one", 1, path))
    with pytest.raises(RuntimeError, match="model failure"):
        detector.process_keyframe(KeyframeInput("two", 2, path))
    assert len(detector.index.frames) == 1
    with pytest.raises(RuntimeError, match="failed"):
        detector.process_keyframe(KeyframeInput("three", 3, path))


def test_cache_is_bounded_and_observations_are_read_only(tmp_path):
    cache = FeatureCache(Engine(), 1)
    one, two = image(tmp_path, "1.png"), image(tmp_path, "2.png")
    assert cache.get(one) is cache.get(one)
    cache.get(two)
    cache.get(one)
    assert (cache.hits, cache.misses) == (1, 3)
    assert (
        cache.bytes_used
        == features().points.nbytes + features().descriptors.nbytes + features().scores.nbytes
    )
    with pytest.raises(ValueError):
        features().points[0, 0] = 9


def test_correspondence_contract_rejects_duplicate_assignments_and_nonfinite_scores():
    with pytest.raises(ValueError, match="one-to-one"):
        CorrespondenceBatch(np.array([[0, 0], [0, 1]], np.int64), np.ones(2, np.float32), "score")
    with pytest.raises(ValueError, match="scores"):
        CorrespondenceBatch(np.array([[0, 0]], np.int64), np.array([np.nan], np.float32), "score")


def test_saved_learned_assignments_reach_geometry_without_rematching_and_are_integrity_checked(
    tmp_path,
):
    import yaml
    from tasks.feature_matching.xyz.evaluator import load_policy

    camera = tmp_path / "sequence/mav0/cam0"
    (camera / "data").mkdir(parents=True)
    (camera / "sensor.yaml").write_text(
        yaml.safe_dump(
            {
                "camera_model": "pinhole",
                "distortion_model": "radial-tangential",
                "intrinsics": [100, 100, 50, 40],
                "distortion_coefficients": [0, 0, 0, 0],
                "resolution": [100, 80],
            }
        )
    )
    history = KeyframeInput("one", 1, image(camera / "data", "1.png"))
    query = KeyframeInput("two", 30, image(camera / "data", "30.png"))
    assignments = Engine().match(features(), features())
    batch = LoopProposalBatch(
        query, features(), (Candidate(history, 1, 0.9, assignments, features()),), 1
    )
    root = tmp_path / "learned"
    writer = EvidenceWriter(root, {"variant": "LDO-fixture"})
    writer.append(batch)
    writer.finalize()
    source = SavedCorrespondences(root)
    policy = load_policy(Path("evaluation/src/tasks/feature_matching/xyz/config.yaml"))
    geometry = ImageGeometry(tmp_path / "sequence", policy, root, source)
    result = geometry.check(query.image_reference, history.image_reference, np.eye(4), 0)
    assert result["measurements"]["match_count"] == 1
    point = result["feature_matches"][0]
    np.testing.assert_array_equal(point["query_feature_xy"], [20, 30])
    np.testing.assert_array_equal(point["historical_feature_xy"], [40, 50])
    assert point["matcher_score"] == pytest.approx(0.8)
    assert "hamming_distance" not in point
    (root / "pair_30_1.npz").write_bytes(b"changed")
    with pytest.raises(ValueError, match="manifest"):
        geometry.check(query.image_reference, history.image_reference, np.eye(4), 0)


def test_config_rejects_unknown_keys_and_mismatched_feature_counts(tmp_path):
    import yaml

    raw = yaml.safe_load(Path("ldo/configs/megaloc_lightglue.yaml").read_text())
    raw["accidental_setting"] = True
    path = tmp_path / "bad.yaml"
    path.write_text(yaml.safe_dump(raw))
    with pytest.raises(ValueError, match="configuration keys"):
        load_config(path)
    with pytest.raises(ValueError, match="lengths"):
        LocalFeatures(
            np.zeros((2, 2), np.float32),
            np.ones((1, 2), np.float32),
            np.ones(2, np.float32),
            (100, 80),
            "f",
            "v",
        )


def test_report_attributes_learned_results_correctly_without_claiming_loop_accuracy():
    review = {
        "status": "complete",
        "checked_pairs": 1,
        "excluded_pairs": 0,
        "feature_totals": {"supported": 3, "contradicted": 1, "untestable": 2},
        "provenance": {
            "model_manifest": {"variant": "LDO-MegaLoc-LightGlue"},
            "policy": {"stereo_world_mahalanobis_squared_maximum": 11.345},
        },
    }
    report = "\n".join(_feature_review(review))
    assert "LDO-MegaLoc-LightGlue" in report
    assert "same pinned stereo" in report
    assert "25.00%" in report
    assert "66.67%" in report
    assert "do not declare an entire loop candidate" in report


def test_original_xyz_and_policy_files_are_unchanged_from_orb_run():
    from ldo.artifacts import sha256

    baseline = Path(
        "evaluation/output/native/orb_dbow2/235a491f670f4f718db1f2725310c0b4_8089595b7ba24a66ad5e77377de3293f/candidate_checks/provenance.json"
    )
    if not baseline.exists():
        pytest.skip("Local historical baseline artifacts are not distributed with the code")
    provenance = json.loads(baseline.read_text())
    # Stereo preparation now has audited field-of-view recovery. The numerical
    # verdict and its thresholds must still match the historical benchmark.
    for filename in ("xyz.py", "config.yaml"):
        path = Path("evaluation/src/tasks/feature_matching/xyz") / filename
        expected = next(
            value
            for name, value in provenance["input_and_code_sha256"].items()
            if name.endswith(f"candidate_evaluator/{filename}")
        )
        assert sha256(path) == expected, filename


def test_numerical_stereo_geometry_is_unchanged_by_field_of_view_recovery():
    import ast

    old = Path(
        "evaluation/output/native/ldo/d0ff54f202a24ecfb9eba28755608dba_8436716ed3494b91a770243e451b2080/source/evaluation/src/modules/candidate_evaluator/stereo.py"
    )
    if not old.is_file():
        pytest.skip("Local historical source snapshot is not distributed with the code")
    new = Path("evaluation/src/tasks/feature_matching/xyz/stereo.py")
    functions = ("project", "triangulate", "reconstruct", "compare_landmarks")
    trees = [
        {
            node.name: ast.dump(node)
            for node in ast.parse(path.read_text()).body
            if isinstance(node, ast.FunctionDef) and node.name in functions
        }
        for path in (old, new)
    ]
    assert set(trees[0]) == set(functions)
    assert trees[0] == trees[1]


def test_benchmark_normalizes_relative_configuration_before_source_snapshot():
    from benchmarks.ldo.benchmark import LDOBenchmark

    class Publisher:
        def publish(self, *args):
            raise AssertionError("Constructing a benchmark must not publish measurements")

    benchmark = LDOBenchmark(
        Path("evaluation/src/benchmarks/ldo/smoke.yaml"), publisher=Publisher()
    )
    assert benchmark.config_path.is_absolute()
    assert benchmark.config_path.is_relative_to(benchmark.root)


def test_report_can_reference_evidence_outside_its_output_directory(tmp_path):
    from modules.evaluation_file_handler.handler import artifact_reference

    report_directory = tmp_path / "reports"
    evidence = tmp_path / "separate-artifacts/example.png"
    reference = artifact_reference(str(evidence), report_directory)
    assert (report_directory / reference).resolve() == evidence.resolve()
