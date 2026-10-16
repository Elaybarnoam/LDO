"""Resolve research assets without relying on the caller's working directory.

An explicit LDO_PROJECT_ROOT takes precedence over the detected checkout. Installed
wheels read bundled default configurations. Full dataset/model workflows still
require an explicit checkout and their separately installed external runtimes.
"""

import os
from importlib.resources import files
from pathlib import Path


def project_root() -> Path:
    """Return an explicit root, the source checkout, or the caller's work directory."""
    override = os.environ.get("LDO_PROJECT_ROOT")
    if override:
        root = Path(override).expanduser().resolve()
        if not (root / "pyproject.toml").is_file():
            raise ValueError("LDO_PROJECT_ROOT must point to a project checkout")
        return root
    for root in Path(__file__).resolve().parents:
        if (root / "pyproject.toml").is_file() and (root / "src/loop_eval").is_dir():
            return root
    return Path.cwd().resolve()


def configuration_path(relative: str) -> Path:
    """Resolve a configs/ path from a checkout or read-only wheel resources."""
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0] != "configs":
        raise ValueError("Expected a relative path within configs/")
    config_root = os.environ.get("LDO_CONFIG_ROOT")
    if config_root:
        candidate = Path(config_root).expanduser().resolve().joinpath(*path.parts[1:])
        if not candidate.is_file():
            raise FileNotFoundError(f"Configuration missing from LDO_CONFIG_ROOT: {candidate}")
        return candidate
    candidate = project_root() / path
    if candidate.is_file():
        return candidate
    bundled = files("ldo_research_resources")
    for part in path.parts:
        bundled = bundled.joinpath(part)
    if bundled.is_file():
        return Path(str(bundled))
    raise FileNotFoundError(f"Configuration not available: {relative}")
