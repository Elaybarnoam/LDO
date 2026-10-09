import argparse
from pathlib import Path

from .adapter import ORBDBoW2Benchmark


def main():
    parser = argparse.ArgumentParser(description="Standalone ORB + DBoW2 retrieval")
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("config.yaml"))
    return ORBDBoW2Benchmark(parser.parse_args().config).run()


if __name__ == "__main__":
    raise SystemExit(main())
