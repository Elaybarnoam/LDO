import argparse
from pathlib import Path

from tasks.loop_closure.comparison.cli import ROOT, load_config
from tasks.loop_closure.verification import run_verification

from benchmarks.base import Benchmark


class LoopVerificationBenchmark(Benchmark):
    def __init__(self, args):
        super().__init__()
        self.args = args

    def execute(self):
        config = load_config(self.args.config)
        self.sequence_id = Path(config["reference"]["sequence"]).name
        result = run_verification(
            config,
            self.args.verifier_config,
            self.args.stereo_config,
            self.args.assessment_config,
            self.args.query_limit,
            self.args.selected_queries,
            on_event=self.publish,
            on_log=self.log,
            fixed_root=self.args.fixed_checks,
        )
        return {"artifact_directory": result["verified_connections"]["artifact_directory"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument(
        "--verifier-config", type=Path, default=ROOT / "loop_verification/config.yaml"
    )
    parser.add_argument(
        "--stereo-config", type=Path, default=ROOT / "loop_verification/stereo.yaml"
    )
    parser.add_argument(
        "--assessment-config",
        type=Path,
        default=ROOT / "evaluation/src/tasks/loop_closure/assessment.yaml",
    )
    parser.add_argument("--query-limit", type=int)
    parser.add_argument("--selected-queries", action="store_true")
    parser.add_argument("--fixed-checks", type=Path)
    args = parser.parse_args()
    raise SystemExit(LoopVerificationBenchmark(args).run())


if __name__ == "__main__":
    main()
