"""Install, prepare and run a versioned reference-geometry benchmark."""

import argparse
import json
import math
import re
import shutil
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[4]


def validate_config(config):
    """Fail before download/inference on malformed or unsafe protocol settings."""
    if not isinstance(config, dict) or config.get("version") != 1:
        raise ValueError("Reference geometry configuration requires version 1")
    dataset, policy = config["dataset"], config["protocol"]
    for key in ("environment", "difficulty"):
        if not re.fullmatch(r"[A-Za-z0-9_-]+", dataset[key]):
            raise ValueError(f"Unsafe dataset path component: {key}")
    trajectories = dataset["trajectories"]
    if (
        not trajectories
        or len(set(trajectories)) != len(trajectories)
        or any(not re.fullmatch(r"P[0-9]{3}", t) for t in trajectories)
    ):
        raise ValueError("Require distinct explicit trajectory IDs")
    if not re.fullmatch(r"[0-9a-f]{40}", dataset["revision"]):
        raise ValueError("Dataset revision must be a pinned commit")
    for key, value in policy.items():
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError(f"Invalid numeric policy: {key}")
        if value < 0 or (key != "seed" and value == 0):
            raise ValueError(f"Invalid positive policy: {key}")
    for key in ("seed", "frame_stride", "top_k", "exclusion_ns", "event_gap_ns", "grid_step"):
        if type(policy[key]) is not int:
            raise ValueError(f"Policy must be an integer: {key}")
    for key in (
        "loop_overlap",
        "target_precision",
        "depth_relative_tolerance",
        "depth_edge_relative_tolerance",
    ):
        if policy[key] > 1:
            raise ValueError(f"Invalid fractional policy: {key}")
    if policy["minimum_depth_m"] >= policy["maximum_depth_m"] or policy["grid_step"] >= 640:
        raise ValueError("Invalid depth range or sampling grid")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("install", "prepare", "run", "evaluate", "pipeline", "report")
    )
    parser.add_argument(
        "--config", type=Path, default=ROOT / "evaluation/src/tasks/reference_geometry/config.yaml"
    )
    parser.add_argument("--prepared", type=Path)
    parser.add_argument(
        "--results", type=Path, help="Completed benchmark summary.json to report without inference"
    )
    args = parser.parse_args()
    config = yaml.safe_load(args.config.read_text())
    validate_config(config)
    if args.command == "evaluate":
        if args.results is None:
            parser.error("evaluate requires --results containing saved detector evidence")
        from .direct import evaluate_saved

        print(evaluate_saved(config, args.config, args.results))
    elif args.command == "report":
        if args.results is None:
            parser.error("report requires --results")
        from tasks.loop_closure.comparison.cli import publish_report
        from tasks.loop_closure.comparison.reference import sha256

        from .depth_coverage import summarize
        from .reporting import aggregate, audit_constraints
        from .workflow import local

        result = json.loads(args.results.read_text())
        task = result["reference_geometry"]
        if task["manifest"]["protocol"] != config["protocol"]:
            raise ValueError("Report protocol differs from completed benchmark")
        if task.get("mode") == "reference_features":
            from .direct_report import aggregate as aggregate_features

            task["aggregate"] = aggregate_features(task["sequences"], config["protocol"]["top_k"])
            print(publish_report(result, local(config["output"]), args.config))
            return
        audit_constraints(task)
        task["aggregate"] = aggregate(task["sequences"], config["protocol"]["top_k"])
        task["depth_coverage"] = summarize(
            task["sequences"], task["artifact_directory"], config["protocol"]
        )
        task["depth_coverage_source_sha256"] = sha256(Path(__file__).with_name("depth_coverage.py"))
        task["reporting_source_sha256"] = sha256(Path(__file__).with_name("reporting.py"))
        analysis = (
            Path(task["artifact_directory"])
            / "report_analysis"
            / task["reporting_source_sha256"][:12]
        )
        analysis.mkdir(parents=True, exist_ok=True)
        for name in ("cli.py", "reporting.py", "depth_coverage.py"):
            shutil.copyfile(Path(__file__).with_name(name), analysis / name)
        (analysis / "inputs.json").write_text(
            json.dumps(
                {
                    "completed_summary_sha256": sha256(args.results),
                    "report_config_sha256": sha256(args.config),
                    "source_sha256": {
                        name: sha256(analysis / name)
                        for name in ("cli.py", "reporting.py", "depth_coverage.py")
                    },
                },
                indent=2,
            )
        )
        task["report_analysis_directory"] = str(analysis)
        print(publish_report(result, local(config["output"]), args.config))
    elif args.command == "install":
        from .install import install

        result = install(config["dataset"])
        index = ROOT / "evaluation/datasets/tartanair_v2"
        index.mkdir(parents=True, exist_ok=True)
        (index / "installation.json").write_text(json.dumps(result, indent=2))
        print(json.dumps(result, indent=2))
    else:
        from .workflow import prepare, run, run_pipeline

        if args.command == "prepare":
            print(prepare(config, args.config))
        elif args.command == "pipeline":
            print(run_pipeline(config, args.config, args.prepared))
        else:
            print(run(config, args.config, args.prepared))
