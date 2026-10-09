"""Windows convenience launcher: the entire evaluation runs inside WSL."""

import argparse
import os
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--distribution", default="Ubuntu-24.04")
    parser.add_argument("--python", default="/opt/loop-detector/python-env/bin/python")
    args = parser.parse_args()
    if os.name != "nt":
        parser.error("Use evaluation/src/runner.py directly inside Linux")
    project = Path(__file__).resolve().parents[1]
    linux_project = subprocess.check_output(["wsl.exe", "-d", args.distribution, "--", "wslpath", "-a", str(project)],
                                            text=True, encoding="utf-8").strip()
    return subprocess.call(["wsl.exe", "-d", args.distribution, "--cd", linux_project, "--",
                            args.python, "evaluation/src/runner.py"])


if __name__ == "__main__":
    raise SystemExit(main())
