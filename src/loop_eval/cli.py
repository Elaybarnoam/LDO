"""Installed commands for diagnosis, synthetic replay, and research workflows."""

import argparse
import importlib.metadata
import importlib.util
import json
import os
import platform
import runpy
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from .paths import project_root

WORKFLOWS = {
    "reference": "loop_eval.tasks.reference_geometry.cli",
    "compare": "loop_eval.tasks.loop_closure.comparison.cli",
    "matching": "loop_eval.tasks.matching_optimization.workflow",
    "depth-v2": "loop_eval.tasks.reference_depth_v2.workflow",
    "diagnostics": "loop_eval.tasks.matching_diagnostics",
    "descriptors": "loop_eval.tasks.descriptor_analysis",
    "image-pairs": "loop_eval.tasks.image_pair_matching",
}


def doctor(model_root: Path | None = None, probe_cuda: bool = False) -> dict:
    """Inspect local prerequisites without importing models or downloading assets."""
    versions: dict[str, str | None] = {}
    for name in (
        "visual-imu-loop-detector",
        "numpy",
        "scipy",
        "opencv-python",
        "opencv-python-headless",
        "torch",
        "lightglue",
    ):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    result: dict[str, Any] = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "project_root": str(project_root()),
        "packages": versions,
        "executables": {name: shutil.which(name) for name in ("uv", "wsl", "cmake", "nvidia-smi")},
        "cuda": "Not probed; use nvidia-smi and the model environment for hardware validation",
        "runtime": {
            key: os.environ.get(key)
            for key in (
                "LDO_PROJECT_ROOT",
                "LDO_CONFIG_ROOT",
                "LDO_MODEL_ROOT",
                "LDO_WSL_DISTRO",
                "LDO_WSL_PYTHON",
            )
        },
        "model_package_available": importlib.util.find_spec("torch") is not None,
    }
    if model_root is not None:
        from ldo.artifacts import verify_install

        try:
            manifest = verify_install(model_root.expanduser().resolve())
            result["model_integrity"] = {
                "ok": True,
                "artifacts_checked": len(manifest["artifacts"]),
            }
        except (OSError, ValueError, KeyError) as error:
            result["model_integrity"] = {"ok": False, "reason": str(error)}
    if probe_cuda:
        try:
            probe = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=name,driver_version,memory.total",
                    "--format=csv,noheader",
                ],
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            )
            result["cuda"] = {
                "driver_probe_ok": True,
                "devices": probe.stdout.strip().splitlines(),
                "scope": "Driver/device visibility only; not model-runtime compatibility",
            }
        except (OSError, subprocess.SubprocessError) as error:
            result["cuda"] = {"driver_probe_ok": False, "reason": str(error)}
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("doctor", "smoke", "configure", *WORKFLOWS))
    arguments = sys.argv[1:]
    args = parser.parse_args(arguments[:1])
    remaining = arguments[1:]
    if args.command == "doctor":
        diagnostic_parser = argparse.ArgumentParser(description=doctor.__doc__)
        diagnostic_parser.add_argument(
            "--model-root", type=Path, help="Verify every installed model artifact hash"
        )
        diagnostic_parser.add_argument(
            "--probe-cuda", action="store_true", help="Query driver visibility with nvidia-smi"
        )
        options = diagnostic_parser.parse_args(remaining)
        result = doctor(options.model_root, options.probe_cuda)
        print(json.dumps(result, indent=2))
        if result.get("model_integrity", {}).get("ok") is False or (
            options.probe_cuda and result["cuda"]["driver_probe_ok"] is False
        ):
            raise SystemExit(1)
    elif args.command == "configure":
        from .runtime import main as configure_main

        configure_main(remaining)
    elif args.command == "smoke":
        from .smoke import main as smoke_main

        smoke_main(remaining)
    else:
        # Forward to the established task implementation rather than duplicate it.
        sys.argv = [f"ldo-research {args.command}", *remaining]
        module = WORKFLOWS[args.command]
        if args.command in {"reference", "compare"}:
            from importlib import import_module

            import_module(module).main()
        else:
            runpy.run_module(module, run_name="__main__")


if __name__ == "__main__":
    main()
