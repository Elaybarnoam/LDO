"""Thin entry point for independent reference-depth detector experiments."""

import sys

from loop_eval.tasks.loop_closure.comparison.launcher import launch  # noqa: E402
from loop_eval.tasks.reference_geometry.cli import main  # noqa: E402

if __name__ == "__main__":
    code = launch(sys.argv[1:], "evaluation/reference_geometry.py")
    if code is None:
        main()
    else:
        raise SystemExit(code)
