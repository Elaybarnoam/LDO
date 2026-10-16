"""Comparison orchestration; report writing stays in the existing FIFO handler."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

import yaml

from loop_eval.infrastructure.evaluation_file_handler.handler import EvaluationFileHandler
from loop_eval.paths import project_root

from .comparison import compare
from .reference import prepare, sha256

ROOT = project_root()


def load_config(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if (
        set(data) != {"version", "protocol", "reference", "methods", "matching", "output"}
        or data["version"] != 1
    ):
        raise ValueError("Invalid comparison configuration")
    p = data["protocol"]
    expected = {
        "seed",
        "exclusion_ns",
        "pose_tolerance_ms",
        "query_stride",
        "k_values",
        "bootstrap_block_queries",
        "bootstrap_samples",
    }
    if set(p) != expected:
        raise ValueError("Invalid comparison protocol")
    for key in expected - {"k_values"}:
        if type(p[key]) is not int or p[key] < (0 if key == "seed" else 1):
            raise ValueError(f"Invalid protocol integer: {key}")
    if (
        not isinstance(p["k_values"], list)
        or not p["k_values"]
        or any(type(k) is not int or not 1 <= k <= 100 for k in p["k_values"])
        or p["k_values"] != sorted(set(p["k_values"]))
    ):
        raise ValueError("K values must be unique increasing positive budgets")
    if set(data["methods"]) != {"orb", "ldo"}:
        raise ValueError("Configure both orb and ldo")
    for section, keys in (
        ("reference", {"root", "sequence", "replay"}),
        ("matching", {"ldo_config", "xyz_config", "orb_feature_root", "orb_config"}),
    ):
        if set(data[section]) != keys:
            raise ValueError(f"Invalid {section} settings")
        for key in keys:
            data[section][key] = resolve(data[section][key])
    for method in data["methods"].values():
        if set(method) != {"trace", "replay", "checks"}:
            raise ValueError("Invalid method paths")
        for key, value in method.items():
            method[key] = resolve(value) if value else None
    data["output"] = resolve(data["output"])
    return data


def resolve(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("Configured path must be nonempty")
    path = Path(value)
    return str(path if path.is_absolute() else ROOT / path)


def publish_report(result: dict, root: Path, config_path: Path) -> Path:
    now = datetime.now(UTC)
    local = now.astimezone(ZoneInfo("Asia/Jerusalem"))
    run_id = uuid4().hex
    path = root / f"comparison_{local.strftime('%Y-%m-%d_%H-%M-%S_%f')}_{run_id[:8]}.json"
    handler = EvaluationFileHandler(
        path,
        {
            "run_id": run_id,
            "started_at": local.isoformat(),
            "timezone": "Asia/Jerusalem",
            "comparison_config_sha256": sha256(config_path),
        },
        ["comparison"],
    )
    try:
        shutil.copyfile(config_path, handler.artifact_dir / "comparison-config.yaml")
        if result.get("reference_path"):
            reference = Path(result["reference_path"])
            snapshot = handler.artifact_dir / "reference"
            snapshot.mkdir()
            for name in (
                "manifest.json",
                "pairs.jsonl",
                "reviews.jsonl",
                "policy.yaml",
                "events.json",
                "interval_reviews.jsonl",
                "proposals.jsonl",
                "preparation.json",
            ):
                if (reference / name).exists():
                    shutil.copyfile(reference / name, snapshot / name)
        source = handler.artifact_dir / "source"
        source.mkdir()
        for source_path in Path(__file__).parent.glob("*.py"):
            shutil.copyfile(source_path, source / source_path.name)
        task_source = source / "loop_closure"
        task_source.mkdir()
        for source_path in Path(__file__).parent.parent.glob("*.py"):
            shutil.copyfile(source_path, task_source / source_path.name)
        revisit_source = task_source / "revisits"
        revisit_source.mkdir()
        for source_path in (Path(__file__).parent.parent / "revisits").glob("*.py"):
            shutil.copyfile(source_path, revisit_source / source_path.name)
        handler.enqueue(
            "comparison",
            {
                "protocol_version": 1,
                "run_id": run_id,
                "benchmark_id": "comparison",
                "event_number": 1,
                "event_type": "comparison_result",
                "payload": result,
                "dataset_timestamp_ns": None,
                "sequence_id": result["sequence"],
            },
        )
        handler.record_status("comparison", status="completed")
    except BaseException as error:
        handler.close("failed", str(error))
        raise
    else:
        handler.close("completed")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=(
            "prepare",
            "review",
            "compare",
            "match",
            "aggregate",
            "verify",
            "audit",
            "diagnose",
            "revisits-prepare",
            "revisits-review",
            "revisits-import",
            "revisits-freeze",
            "revisits-evaluate",
            "revisits-select",
            "revisits-aggregate",
        ),
    )
    parser.add_argument(
        "--verifier-config", type=Path, default=ROOT / "configs/verification/config.yaml"
    )
    parser.add_argument(
        "--stereo-config", type=Path, default=ROOT / "configs/verification/stereo.yaml"
    )
    parser.add_argument(
        "--assessment-config",
        type=Path,
        default=ROOT / "configs/evaluation/loop_closure/assessment.yaml",
    )
    parser.add_argument(
        "--query-limit", type=int, help="Smoke-test only; default processes the full replay"
    )
    parser.add_argument(
        "--selected-queries",
        action="store_true",
        help="Process only independently selected reference queries",
    )
    parser.add_argument(
        "--reports", type=Path, nargs="+", help="Per-sequence comparison JSON reports"
    )
    parser.add_argument(
        "--config", type=Path, default=ROOT / "configs/evaluation/loop_closure/config.yaml"
    )
    parser.add_argument(
        "--verification-report",
        type=Path,
        help="Completed shared-verifier report to audit against all external XYZ evidence",
    )
    parser.add_argument(
        "--revisit-policy",
        type=Path,
        default=ROOT / "configs/evaluation/loop_closure/revisits/policy.yaml",
    )
    parser.add_argument("--frozen-reference", type=Path)
    parser.add_argument("--snapshot-output", type=Path)
    parser.add_argument("--decisions", type=Path, help="Independent interval review JSONL")
    parser.add_argument("--operating-points", type=Path)
    parser.add_argument("--reviewer")
    parser.add_argument(
        "--supervised",
        action="store_true",
        help="Run verification through the process orchestrator and FIFO writer",
    )
    parser.add_argument(
        "--retrieval-only", action="store_true", help="Skip reading existing XYZ feature evidence"
    )
    parser.add_argument("--pair-limit", type=int, default=20)
    parser.add_argument("--feature-budget", type=int, help="Re-extract both methods with this cap")
    parser.add_argument("--fixed-checks", type=Path, help="Completed match output directory")
    args = parser.parse_args()
    if (
        args.command.startswith("revisits-")
        and args.config == ROOT / "configs/evaluation/loop_closure/config.yaml"
    ):
        args.config = ROOT / "configs/evaluation/loop_closure/revisit_config.yaml"
    config = load_config(args.config)
    reference = Path(config["reference"]["root"])
    if args.command.startswith("revisits-"):
        from loop_eval.tasks.loop_closure.revisits import reference as event_reference
        from loop_eval.tasks.loop_closure.revisits import workflow

        if args.command == "revisits-prepare":
            print(
                json.dumps(event_reference.prepare_revisits(config, args.revisit_policy), indent=2)
            )
        elif args.command == "revisits-review":
            from loop_eval.tasks.loop_closure.revisits.review import review

            if not args.reviewer:
                parser.error("--reviewer is required")
            review(reference, args.reviewer)
        elif args.command == "revisits-import":
            if not args.decisions:
                parser.error("--decisions is required")
            _, records = event_reference.load_reference(reference)
            decisions = [
                json.loads(line) for line in args.decisions.read_text(encoding="utf-8").splitlines()
            ]
            for decision in decisions:
                event_reference.validate_review(decision, records)
            for decision in decisions:
                event_reference.append_review(reference, decision)
            print(f"Imported {len(decisions)} independent decisions")
        elif args.command == "revisits-freeze":
            target = args.snapshot_output or reference / "snapshots" / f"reference_{uuid4().hex}"
            print(json.dumps(event_reference.freeze(reference, target), indent=2))
            print(f"Frozen reference: {target}")
        elif args.command == "revisits-aggregate":
            if not args.reports:
                parser.error("--reports is required")
            print(
                publish_report(
                    workflow.aggregate(args.reports), Path(config["output"]), args.config
                )
            )
        else:
            if not args.frozen_reference:
                parser.error("--frozen-reference is required")
            if args.command == "revisits-select" and args.operating_points:
                parser.error("Development selection cannot also apply held-out operating points")
            select_path = (
                Path(config["output"]) / f"operating_points_{uuid4().hex}.json"
                if args.command == "revisits-select"
                else None
            )
            result = workflow.report(
                config,
                args.frozen_reference,
                args.verification_report,
                args.operating_points,
                select_path,
            )
            print(publish_report(result, Path(config["output"]), args.config))
            if select_path:
                print(f"Development operating points: {select_path}")
    elif args.command == "verify":
        if args.supervised:
            from loop_eval.infrastructure.orchestrator.orchestrator import Orchestrator

            supervised = yaml.safe_load(
                (ROOT / "configs/evaluation/loop_closure/run.yaml").read_text()
            )
            command = supervised["benchmarks"][0]["command"]
            command[command.index("--config") + 1] = str(args.config.resolve())
            for flag, value in (
                ("--verifier-config", args.verifier_config),
                ("--stereo-config", args.stereo_config),
                ("--assessment-config", args.assessment_config),
            ):
                command.extend([flag, str(value.resolve())])
            if args.query_limit is not None:
                command.extend(["--query-limit", str(args.query_limit)])
            if args.selected_queries:
                command.append("--selected-queries")
            if args.fixed_checks:
                command.extend(["--fixed-checks", str(args.fixed_checks.resolve())])
            supervised["output"]["root"] = config["output"]
            run_path = Path(config["output"]) / f"loop_verification_run_{uuid4().hex}.yaml"
            run_path.parent.mkdir(parents=True, exist_ok=True)
            with run_path.open("x") as stream:
                yaml.safe_dump(supervised, stream)
            Orchestrator(run_path).run()
            return
        from loop_eval.tasks.loop_closure.verification import run_verification

        result = run_verification(
            config,
            args.verifier_config.resolve(),
            args.stereo_config.resolve(),
            args.assessment_config.resolve(),
            args.query_limit,
            args.selected_queries,
            on_log=print,
            fixed_root=args.fixed_checks,
        )
        print(publish_report(result, Path(config["output"]), args.config))
    elif args.command == "diagnose":
        from loop_eval.tasks.loop_closure.connection_diagnostics import diagnose

        if not args.verification_report:
            parser.error("--verification-report must name a completed full verifier/XYZ audit")
        result = diagnose(config, args.verification_report)
        print(publish_report(result, Path(config["output"]), args.config))
    elif args.command == "audit":
        from loop_eval.tasks.loop_closure.disagreement import audit

        if not args.verification_report:
            parser.error("--verification-report is required")
        result = audit(config, args.verification_report)
        print(publish_report(result, Path(config["output"]), args.config))
    elif args.command == "aggregate":
        from .suite import aggregate

        if not args.reports:
            parser.error("--reports is required")
        print(publish_report(aggregate(args.reports), Path(config["output"]), args.config))
    elif args.command == "prepare":
        prepare(
            Path(config["reference"]["sequence"]),
            Path(config["reference"]["replay"]),
            reference,
            config["protocol"],
        )
        print(f"Independent reference prepared: {reference}. All labels start unknown.")
    elif args.command == "review":
        from .review import review

        if not args.reviewer:
            parser.error("--reviewer is required")
        review(reference, args.reviewer)
    elif args.command == "match":
        from .matching import match_fixed

        if args.pair_limit < 1:
            parser.error("--pair-limit must be positive")
        if args.feature_budget is not None and not 1 <= args.feature_budget <= 10000:
            parser.error("--feature-budget must be in [1, 10000]")
        output = Path(config["output"]) / f"fixed_matching_{uuid4().hex}"
        matching = match_fixed(reference, config, output, args.pair_limit, args.feature_budget)
        result = compare(
            reference,
            {
                n: {**paths, "checks": str(output / n / "candidate_checks")}
                for n, paths in config["methods"].items()
            },
            config["protocol"],
            fixed=True,
        )
        result["matching_experiment"] = matching
        print(publish_report(result, Path(config["output"]), args.config))
    else:
        methods = config["methods"]
        if args.retrieval_only:
            if args.fixed_checks:
                parser.error("--retrieval-only cannot be combined with --fixed-checks")
            methods = {n: {**p, "checks": None} for n, p in methods.items()}
        if args.fixed_checks:
            methods = {
                n: {**p, "checks": str(args.fixed_checks / n / "candidate_checks")}
                for n, p in methods.items()
            }
        result = compare(reference, methods, config["protocol"], fixed=bool(args.fixed_checks))
        if args.fixed_checks:
            result["matching_experiment"] = json.loads(
                (args.fixed_checks / "manifest.json").read_text()
            )
        print(publish_report(result, Path(config["output"]), args.config))


if __name__ == "__main__":
    main()
