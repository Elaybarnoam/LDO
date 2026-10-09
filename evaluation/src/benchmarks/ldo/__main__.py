"""Run the selected LDO benchmark configuration."""

import argparse
from pathlib import Path

from .benchmark import LDOBenchmark


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("config.yaml"))
    return LDOBenchmark(parser.parse_args().config).run()


if __name__ == "__main__":
    raise SystemExit(main())
