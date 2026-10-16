import argparse
from pathlib import Path

from loop_eval.paths import configuration_path

from .adapter import ORBDBoW2Benchmark


def main():
    parser = argparse.ArgumentParser(description="Standalone ORB + DBoW2 retrieval")
    parser.add_argument(
        "--config",
        type=Path,
        default=configuration_path("configs/benchmarks/orb_dbow2/config.yaml"),
    )
    return ORBDBoW2Benchmark(parser.parse_args().config).run()


if __name__ == "__main__":
    raise SystemExit(main())
