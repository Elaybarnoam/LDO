"""Recheck any saved detector trace independently of benchmark execution."""

import argparse
import json
import sys
from pathlib import Path

from loop_eval.paths import configuration_path

from .evaluator import check_trace


def main():
    parser = argparse.ArgumentParser(description="Independent candidate evidence checker")
    for argument in ("sequence", "replay", "trace", "output"):
        parser.add_argument(f"--{argument}", type=Path, required=True)
    parser.add_argument(
        "--config",
        type=Path,
        default=configuration_path("configs/evaluation/feature_matching/xyz/config.yaml"),
    )
    parser.add_argument(
        "--feature-root", type=Path, required=True, help="Upstream ORB exports and manifest"
    )
    args = parser.parse_args()
    result = check_trace(
        args.sequence,
        args.replay,
        args.trace,
        args.output,
        args.config,
        feature_root=args.feature_root,
        on_log=lambda message: print(message, file=sys.stderr, flush=True),
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
