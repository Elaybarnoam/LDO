"""Installed CPU workflow, configuration isolation, and scientific preservation."""

import hashlib
import json
from pathlib import Path

import pytest
import yaml

from ldo.configuration import POLICIES, load_config
from loop_eval.cli import doctor
from loop_eval.paths import configuration_path, project_root
from loop_eval.runtime import materialize
from loop_eval.smoke import replay


def test_cpu_replay_is_causal_and_explicitly_not_a_research_result():
    result = replay()
    assert result["research_result"] is False
    assert [row["eligible"] for row in result["frames"]] == [0, 0, 1, 2]
    assert result["frames"][-1]["candidates"] == ["0", "1"]
    assert result["frames"][-1]["matches"] == [2, 2]


def test_archived_candidate_policy_recipe_resolves_its_frozen_parameters():
    config = load_config(configuration_path("configs/models/optimized-policy.yaml"))
    assert config.policy_parameters.is_file()
    assert POLICIES[config.policy](config) is not None


def test_runtime_profile_preserves_numeric_policy_and_refuses_replacement(tmp_path, monkeypatch):
    monkeypatch.delenv("LDO_CONFIG_ROOT", raising=False)
    output = tmp_path / "configs"
    count = materialize(output, "/home/research/runtime")
    assert count >= 20
    original = yaml.safe_load(
        configuration_path("configs/models/optimized-confidence.yaml").read_text()
    )
    changed = yaml.safe_load((output / "models/optimized-confidence.yaml").read_text())
    assert changed.pop("model_root") == "/home/research/runtime/ldo-models"
    original.pop("model_root")
    assert changed == original
    reference = yaml.safe_load((output / "evaluation/reference_geometry/config.yaml").read_text())
    assert Path(reference["ldo_config"]).is_file()
    policy = load_config(output / "models/optimized-policy.yaml")
    assert policy.policy_parameters.is_file()
    assert POLICIES[policy.policy](policy) is not None
    with pytest.raises(FileExistsError):
        materialize(output, "/different/runtime")


def test_explicit_config_root_fails_on_missing_default(tmp_path, monkeypatch):
    monkeypatch.setenv("LDO_CONFIG_ROOT", str(tmp_path))
    with pytest.raises(FileNotFoundError, match="LDO_CONFIG_ROOT"):
        configuration_path("configs/models/optimized-confidence.yaml")
    with pytest.raises(ValueError):
        configuration_path("configs/../pyproject.toml")


def test_archive_and_pinned_numerical_bytes_match_baseline():
    root = project_root()
    ledger = json.loads((root / "docs/decisions/migration-ledger.json").read_text())
    pinned = {
        "evaluation/src/tasks/feature_matching/xyz/xyz.py",
        "evaluation/src/tasks/feature_matching/xyz/stereo_worker.py",
        "stereo_observations/stereo_worker.py",
        "evaluation/src/tasks/feature_matching/xyz/config.yaml",
    }
    checked = set()
    for record in ledger["files"]:
        if record["old"].startswith(".docs/") or record["old"] in pinned:
            assert (
                hashlib.sha256((root / record["new"]).read_bytes()).hexdigest()
                == record["original_sha256"]
            ), record["new"]
            checked.add(record["old"])
    assert pinned <= checked


def test_diagnosis_verifies_model_bytes_without_loading_model_libraries(tmp_path):
    weight = tmp_path / "fixture.weights"
    weight.write_bytes(b"fixture artifact")
    (tmp_path / "manifest.json").write_text(
        json.dumps({"artifacts": {weight.name: hashlib.sha256(weight.read_bytes()).hexdigest()}})
    )
    assert doctor(model_root=tmp_path)["model_integrity"]["ok"] is True
    weight.write_bytes(b"changed")
    assert doctor(model_root=tmp_path)["model_integrity"]["ok"] is False
