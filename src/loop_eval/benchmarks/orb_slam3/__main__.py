import argparse
from pathlib import Path

from loop_eval.paths import configuration_path

from .adapter import ORBSLAM3Benchmark


def main() -> int:
    parser = argparse.ArgumentParser(description="Run instrumented ORB-SLAM3 via evaluation IPC")
    parser.add_argument(
        "--config",
        type=Path,
        default=configuration_path("configs/benchmarks/orb_slam3/config.yaml"),
    )
    args = parser.parse_args()
    return ORBSLAM3Benchmark(args.config).run()


if __name__ == "__main__":
    raise SystemExit(main())
