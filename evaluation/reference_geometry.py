"""Thin entry point for independent reference-depth detector experiments."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tasks.loop_closure.comparison.launcher import launch  # noqa: E402
from tasks.reference_geometry.cli import main  # noqa: E402

if __name__ == "__main__":
    code = launch(sys.argv[1:], "evaluation/reference_geometry.py")
    if code is None:
        main()
    else:
        raise SystemExit(code)
