from __future__ import annotations

from pathlib import Path

from project.discovery import CCB_DIRNAME

from .common import CONFIG_FILENAME


def project_config_path(project_root: Path) -> Path:
    return Path(project_root).expanduser().resolve() / CCB_DIRNAME / CONFIG_FILENAME


__all__ = ['project_config_path']
