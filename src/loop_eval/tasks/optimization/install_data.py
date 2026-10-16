"""Predeclared environment split; no detector-driven dataset selection."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from loop_eval.tasks.reference_geometry.install import install

SPLITS = {"train": "RetroOffice", "test": "CountryHouse"}


def main():
    def one(item):
        split, environment = item
        settings = {
            "root": f"/opt/loop-detector/datasets/tartanair_optimization/{split}",
            "repository": "theairlabcmu/tartanair2",
            "revision": "0d2d145e973832742a2aaa04b7d2ebffc8d82817",
            "environment": environment,
            "difficulty": "Data_easy",
            "archives": ["image_lcam_front.zip", "depth_lcam_front.zip", "imu.zip"]
            + (["image_rcam_front.zip"] if split == "test" else []),
        }
        result = install(settings)
        trajectories = sorted(
            p.name
            for p in (Path(settings["root"]) / environment / "Data_easy").glob("P*")
            if p.is_dir()
        )
        print(f"Installed {split}: {environment}, {trajectories}", flush=True)
        return result

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(one, SPLITS.items()))


if __name__ == "__main__":
    main()
