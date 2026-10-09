"""Run inference/analysis in the installed WSL environment; review on Windows."""

import os
import subprocess
from pathlib import Path


def launch(arguments: list[str], script: str = "evaluation/compare.py") -> int | None:
    if (
        os.name != "nt"
        or (arguments and arguments[0] in {"review", "revisits-review"})
        or "--help" in arguments
    ):
        return None
    project = Path(__file__).resolve().parents[5]

    def linux_path(value: str) -> str:
        return subprocess.check_output(
            ["wsl.exe", "-d", "Ubuntu-24.04", "--", "wslpath", "-a", value],
            text=True,
            encoding="utf-8",
        ).strip()

    converted = [linux_path(a) if Path(a).is_absolute() else a for a in arguments]
    return subprocess.call(
        [
            "wsl.exe",
            "-d",
            "Ubuntu-24.04",
            "--cd",
            linux_path(str(project)),
            "--",
            "/opt/loop-detector/ldo-env/bin/python",
            script,
            *converted,
        ]
    )
