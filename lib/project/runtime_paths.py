from __future__ import annotations

from pathlib import Path

from .discovery import project_ccb_dir
from .identity import resolve_project_root


def project_anchor_dir(work_dir: Path | str) -> Path:
    return project_ccb_dir(resolve_project_root(work_dir))


def project_anchor_exists(work_dir: Path | str) -> bool:
    try:
        return project_anchor_dir(work_dir).is_dir()
    except Exception:
        return False


def project_ccbd_dir(work_dir: Path | str) -> Path:
    return project_anchor_dir(work_dir) / 'ccbd'


def project_registry_dir(work_dir: Path | str) -> Path:
    return project_ccbd_dir(work_dir) / 'registry'


def project_lock_dir(work_dir: Path | str) -> Path:
    return project_ccbd_dir(work_dir) / 'locks'


__all__ = [
    'project_anchor_dir',
    'project_anchor_exists',
    'project_ccbd_dir',
    'project_lock_dir',
    'project_registry_dir',
]
