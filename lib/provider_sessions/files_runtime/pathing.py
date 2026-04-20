from __future__ import annotations

from pathlib import Path


CCB_PROJECT_CONFIG_DIRNAME = '.ccb'


def project_config_dir(work_dir: Path) -> Path:
    return Path(work_dir).resolve() / CCB_PROJECT_CONFIG_DIRNAME


def resolve_project_config_dir(work_dir: Path) -> Path:
    return project_config_dir(work_dir)


__all__ = ['CCB_PROJECT_CONFIG_DIRNAME', 'project_config_dir', 'resolve_project_config_dir']
