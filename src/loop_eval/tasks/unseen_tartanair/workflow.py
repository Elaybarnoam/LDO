"""Install, freeze and evaluate two preselected environments without retuning."""

import argparse
import json
import re
import shutil
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import yaml

from loop_eval.paths import configuration_path, project_root
from loop_eval.tasks.loop_closure.comparison.reference import sha256
from loop_eval.tasks.optimization.observations import read_summary
from loop_eval.tasks.reference_geometry.cli import validate_config
from loop_eval.tasks.reference_geometry.detectors import validate_native
from loop_eval.tasks.reference_geometry.direct import run, validate_manifest
from loop_eval.tasks.reference_geometry.direct_report import aggregate
from loop_eval.tasks.reference_geometry.install import install
from loop_eval.tasks.reference_geometry.workflow import prepare

ROOT = project_root()
CONFIG = configuration_path("configs/evaluation/unseen_tartanair/config.yaml")
OUTPUT = ROOT / "evaluation/output/unseen_tartanair"


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".pending.json")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


def freeze():
    settings = yaml.safe_load(CONFIG.read_text())
    if settings["version"] != 1:
        raise ValueError("Unseen benchmark requires version 1")
    names = settings["environments"]
    if (
        len(set(names)) != len(names)
        or not names
        or any(not re.fullmatch(r"[A-Za-z0-9_-]+", n) for n in names)
    ):
        raise ValueError("Require distinct safe environment names")
    _, native, _ = validate_native(ROOT / settings["orb_config"])
    files = [
        CONFIG,
        ROOT / settings["reference_config"],
        ROOT / settings["ldo_config"],
        ROOT / settings["orb_config"],
        native / "manifest.json",
        ROOT / "src/loop_eval/tasks/reference_geometry/geometry.py",
        ROOT / "src/loop_eval/tasks/reference_geometry/direct.py",
        ROOT / "src/loop_eval/tasks/reference_geometry/dataset.py",
        ROOT / "src/loop_eval/tasks/reference_geometry/detectors.py",
        ROOT / "src/ldo/configuration.py",
        ROOT / "src/ldo/matching/lightglue.py",
    ]
    identity = {str(p): sha256(p) for p in files}
    path = OUTPUT / "freeze.json"
    if path.exists():
        stored = json.loads(path.read_text())
        if stored["inputs_sha256"] != identity or stored["settings"] != settings:
            raise ValueError(
                "Frozen unseen experiment changed; use a separate experiment directory"
            )
    else:
        save(
            path,
            {
                "created_at": datetime.now(UTC).isoformat(),
                "settings": settings,
                "inputs_sha256": identity,
                "parameters_selected_before_test": True,
            },
        )
    return settings


def install_all(settings):
    def one(environment):
        dataset = {
            "root": str(Path(settings["dataset_root"]) / environment),
            "repository": settings["repository"],
            "revision": settings["revision"],
            "environment": environment,
            "difficulty": settings["difficulty"],
            "archives": [
                "image_lcam_front.zip",
                "image_rcam_front.zip",
                "depth_lcam_front.zip",
                "imu.zip",
            ],
        }
        installation = install(dataset)
        source = Path(dataset["root"]) / environment / settings["difficulty"]
        names = sorted(p.name for p in source.glob("P[0-9][0-9][0-9]") if p.is_dir())
        if not names or any(not (source / name / "pose_lcam_front.txt").exists() for name in names):
            raise ValueError(f"Missing trajectory/pose inputs: {environment}")
        config = yaml.safe_load((ROOT / settings["reference_config"]).read_text())
        config["dataset"] = {**dataset, "trajectories": names, "reference_only": False}
        config["output"] = str(Path(settings["artifact_root"]) / environment)
        config["ldo_config"], config["orb_config"] = settings["ldo_config"], settings["orb_config"]
        validate_config(config)
        target = OUTPUT / environment / "config.yaml"
        target.parent.mkdir(parents=True, exist_ok=True)
        content = yaml.safe_dump(config, sort_keys=False)
        if target.exists() and target.read_text() != content:
            raise ValueError(
                "Installed trajectory selection differs from frozen environment config"
            )
        target.write_text(content)
        save(
            target.parent / "installation.json",
            {
                "installation": installation,
                "installation_sha256": sha256(Path(dataset["root"]) / "installation.json"),
                "trajectories": names,
                "configuration_sha256": sha256(target),
            },
        )
        print(f"Installed {environment}: {names}", flush=True)

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(one, settings["environments"]))


def prepare_all(settings):
    # Independent environments have independent references; preparation is CPU-only.
    def one(environment):
        directory = OUTPUT / environment
        config_path = directory / "config.yaml"
        config = yaml.safe_load(config_path.read_text())
        installation = json.loads((directory / "installation.json").read_text())
        if sha256(config_path) != installation["configuration_sha256"]:
            raise ValueError("Environment configuration changed")
        marker = directory / "prepared.json"
        if marker.exists():
            value = json.loads(marker.read_text())
            root = Path(value["path"])
            if sha256(root / "manifest.json") != value["sha256"]:
                raise ValueError("Prepared reference changed")
            validate_manifest(json.loads((root / "manifest.json").read_text()), config, config_path)
        else:
            root = prepare(config, config_path)
            save(marker, {"path": str(root), "sha256": sha256(root / "manifest.json")})
        print(f"Prepared all reference labels: {environment}", flush=True)

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(one, settings["environments"]))


def evaluate_all(settings):
    reports, sequences = [], []
    # One GPU inference job at a time to avoid memory contention and timing bias.
    for environment in settings["environments"]:
        freeze()
        directory = OUTPUT / environment
        config_path = directory / "config.yaml"
        config = yaml.safe_load(config_path.read_text())
        installation = json.loads((directory / "installation.json").read_text())
        if sha256(config_path) != installation["configuration_sha256"]:
            raise ValueError("Environment configuration changed")
        prepared = json.loads((directory / "prepared.json").read_text())
        if sha256(Path(prepared["path"]) / "manifest.json") != prepared["sha256"]:
            raise ValueError("Reference manifest changed")
        marker = directory / "completed.json"
        if marker.exists():
            completed = json.loads(marker.read_text())
            path = Path(completed["path"])
            if sha256(path) != completed["sha256"]:
                raise ValueError("Completed model report changed")
        else:
            print(f"Evaluating frozen ORB and confidence-only LDO: {environment}", flush=True)
            path = run(config, config_path, Path(prepared["path"]))
            save(marker, {"path": str(path), "sha256": sha256(path)})
        task = read_summary(path)["reference_geometry"]
        validate_manifest(task["manifest"], config, config_path)
        if (
            task["model_manifest"]["match_threshold"] != 0.3
            or task["model_manifest"]["policy"] != "retrieval_order"
        ):
            raise ValueError("Unexpected LDO variant in unseen results")
        for suffix in (".json", ".md"):
            shutil.copyfile(path.with_suffix(suffix), directory / ("report" + suffix))
        reports.append(
            {
                "environment": environment,
                "report": str(path),
                "report_sha256": sha256(path),
                "task": task,
            }
        )
        sequences.extend(task["sequences"])
        print(f"Completed {environment}: {json.dumps(task['aggregate'])}", flush=True)
    policy = yaml.safe_load((ROOT / settings["reference_config"]).read_text())["protocol"]
    result = {
        "created_at": datetime.now(UTC).isoformat(),
        "environments": reports,
        "aggregate": aggregate(sequences, policy["top_k"]),
        "protocol": policy,
        "freeze_sha256": sha256(OUTPUT / "freeze.json"),
        "test_used_for_tuning": False,
        "ldo_configuration": settings["ldo_config"],
    }
    save(OUTPUT / "results.json", result)
    from .report import publish

    print(publish(result, CONFIG), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("install", "prepare", "run", "all", "report"))
    args = parser.parse_args()
    settings = freeze()
    if args.command in ("install", "all"):
        install_all(settings)
    if args.command in ("prepare", "all"):
        prepare_all(settings)
    if args.command in ("run", "all"):
        evaluate_all(settings)
    if args.command == "report":
        from .report import publish

        print(publish(json.loads((OUTPUT / "results.json").read_text()), CONFIG), flush=True)


if __name__ == "__main__":
    main()
