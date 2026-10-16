"""Run the selected LDO benchmark configuration."""

import argparse
from pathlib import Path

from loop_eval.paths import configuration_path

from .benchmark import LDOBenchmark


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path, default=configuration_path("configs/benchmarks/ldo/config.yaml")
    )
    return LDOBenchmark(parser.parse_args().config).run()


if __name__ == "__main__":
    raise SystemExit(main())
