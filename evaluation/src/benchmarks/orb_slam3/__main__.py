import argparse
from pathlib import Path

from .adapter import ORBSLAM3Benchmark


def main() -> int:
    parser = argparse.ArgumentParser(description="Run instrumented ORB-SLAM3 via evaluation IPC")
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("config.yaml"))
    args = parser.parse_args()
    return ORBSLAM3Benchmark(args.config).run()


if __name__ == "__main__":
    raise SystemExit(main())
