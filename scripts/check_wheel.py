"""Install a built wheel into an isolated target and run it outside the checkout."""

import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from loop_eval.paths import project_root


def main():
    root = project_root()
    wheels = sorted((root / "dist").glob("visual_imu_loop_detector-*.whl"))
    if len(wheels) != 1:
        raise ValueError("Build one current wheel with uv build before this check")
    wheel = wheels[0]
    with zipfile.ZipFile(wheel) as archive:
        required = {
            "ldo/upstream.lock.json",
            "stereo_observations/stereo_worker.py",
            "stereo_observations/stereo-runtime.lock",
            "loop_eval/benchmarks/orb_dbow2/native/CMakeLists.txt",
            "loop_eval/tasks/feature_matching/viewer/geometry_failures.html",
            "ldo_research_resources/configs/models/optimized-confidence.yaml",
        }
        missing = required - set(archive.namelist())
        if missing:
            raise ValueError(f"Wheel missing runtime resources: {sorted(missing)}")
    with tempfile.TemporaryDirectory(prefix="ldo-wheel-") as folder:
        workspace = Path(folder)
        target = workspace / "installed"
        subprocess.run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                sys.executable,
                "--no-deps",
                "--target",
                str(target),
                str(wheel),
            ],
            check=True,
        )
        code = (
            "import sys; from pathlib import Path; "
            "sys.path.insert(0,sys.argv[1]); "
            "import ldo,loop_eval,loop_verification,stereo_observations; "
            "assert Path(ldo.__file__).is_relative_to(Path(sys.argv[1])); "
            "from loop_eval.paths import configuration_path; "
            "p=configuration_path('configs/models/optimized-confidence.yaml'); "
            "assert p.is_relative_to(Path(sys.argv[1])); "
            "from loop_eval.smoke import replay; assert replay()['frames'][-1]['candidates']==['0','1']; "
            "print('Wheel imports, bundled resources, and external-directory smoke passed.')"
        )
        env = {
            key: value
            for key, value in os.environ.items()
            if key not in {"LDO_PROJECT_ROOT", "LDO_CONFIG_ROOT", "LDO_MODEL_ROOT", "PYTHONPATH"}
        }
        subprocess.run(
            [sys.executable, "-I", "-c", code, str(target)], cwd=workspace, env=env, check=True
        )


if __name__ == "__main__":
    main()
