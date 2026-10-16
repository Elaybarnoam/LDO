"""Run inference/analysis in the installed WSL environment; review on Windows."""

import os
import subprocess
from pathlib import Path

from loop_eval.paths import project_root


def launch(arguments: list[str], script: str = "evaluation/compare.py") -> int | None:
    if (
        os.name != "nt"
        or (arguments and arguments[0] in {"review", "revisits-review"})
        or "--help" in arguments
    ):
        return None
    project = project_root()

    def linux_path(value: str) -> str:
        return subprocess.check_output(
            [
                "wsl.exe",
                "-d",
                os.environ.get("LDO_WSL_DISTRO", "Ubuntu-24.04"),
                "--",
                "wslpath",
                "-a",
                value,
            ],
            text=True,
            encoding="utf-8",
        ).strip()

    converted = [linux_path(a) if Path(a).is_absolute() else a for a in arguments]
    return subprocess.call(
        [
            "wsl.exe",
            "-d",
            os.environ.get("LDO_WSL_DISTRO", "Ubuntu-24.04"),
            "--cd",
            linux_path(str(project)),
            "--",
            os.environ.get("LDO_WSL_PYTHON", "/opt/loop-detector/ldo-env/bin/python"),
            script,
            *converted,
        ]
    )
