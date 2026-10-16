"""Fixed-pair denominators and promotion floors must survive variant changes."""

from pathlib import Path

import pytest
import yaml

from ldo.configuration import load_config
from loop_eval.tasks.matching_optimization.metrics import choose, eligible, measure
from loop_eval.tasks.reference_depth_v2.assets import surface_labels

ROOT = Path(__file__).resolve().parents[2]
POLICY = {"minimum_correct_match_retention": 0.9, "minimum_usable_pair_retention": 0.95}


def row(scene, good, bad, label="loop"):
    return {
        "environment": scene,
        "label": label,
        "counts": {"supported": good, "contradicted": bad, "untestable": 0},
    }


def test_empty_match_pairs_are_retained_and_unknown_labels_not_positive():
    result = measure([row("A", 20, 5), row("A", 0, 0), row("A", 0, 0, "unknown")], 20)
    assert result["overall"]["pairs"] == 3
    assert result["overall"]["positive_pairs"] == 2
    assert result["overall"]["usable_positive_pairs"] == 1
    assert result["overall"]["precision"] == 0.8


def test_promotion_cannot_hide_scene_regression_in_pooled_counts():
    base = measure([row("A", 100, 100), row("B", 100, 100)], 20)
    regression = measure([row("A", 180, 20), row("B", 10, 5)], 20)
    assert regression["overall"]["supported"] >= 0.9 * base["overall"]["supported"]
    assert not eligible(base, regression, POLICY)


def test_cumulative_loss_is_measured_against_original_baseline():
    base = measure([row("A", 100, 100)], 20)
    first = measure([row("A", 91, 60)], 20)
    second = measure([row("A", 83, 30)], 20)
    assert eligible(base, first, POLICY)
    assert eligible(first, second, POLICY)
    assert not eligible(base, second, POLICY)


def test_fewer_bad_matches_do_not_promote_lost_usable_pairs():
    base = measure([row("A", 20, 30), row("A", 100, 100)], 20)
    candidate = measure([row("A", 19, 0), row("A", 100, 0)], 20)
    assert not eligible(base, candidate, POLICY)


def test_fit_selection_ignores_validation_scores_and_breaks_ties_deterministically():
    baseline = measure([row("A", 100, 100)], 20)
    previous = {"id": "base", "fit": baseline}
    better = measure([row("A", 95, 30)], 20)
    a = {"id": "a", "fit": better, "validate": "bad"}
    b = {"id": "b", "fit": better, "validate": "good"}
    assert choose([b, a], baseline, previous, POLICY)["id"] == "a"


def test_optional_resize_config_preserves_baseline_and_validates_values(tmp_path):
    config = yaml.safe_load((ROOT / "configs/models/optimized-confidence.yaml").read_text())
    path = tmp_path / "model.yaml"
    path.write_text(yaml.safe_dump(config))
    assert load_config(path).feature_resize is None
    config.update(matching="aliked_lightglue", feature_resize=960)
    path.write_text(yaml.safe_dump(config))
    assert load_config(path).feature_resize == 960
    for value in (True, 0, 0.5, 4096):
        config["feature_resize"] = value
        path.write_text(yaml.safe_dump(config))
        with pytest.raises(ValueError, match="feature_resize"):
            load_config(path)


def test_missing_sky_class_does_not_make_uninterpretable_class_trustworthy():
    labels = surface_labels({"name_map": {"wall": 1, "z": 69}})
    assert labels["name_map"] == {"wall": 1, "sky": -1}
    assert surface_labels({"name_map": {"wall": 1, "sky": 171}})["name_map"]["sky"] == 171
