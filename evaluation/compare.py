"""Thin entry point for independent LDO-versus-ORB evaluation."""

import sys

from loop_eval.tasks.loop_closure.comparison.cli import main  # noqa: E402
from loop_eval.tasks.loop_closure.comparison.launcher import launch  # noqa: E402

if __name__ == "__main__":
    code = launch(sys.argv[1:])
    if code is None:
        main()
    else:
        raise SystemExit(code)
