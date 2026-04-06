from __future__ import annotations

import os
from pathlib import Path

from provider_backends.claude.resolver_runtime.pathing import (
    candidate_project_dirs as _candidate_project_dirs_impl,
    project_key_for_path,
)

from .normalization import normalize_project_path


def _candidate_paths(work_dir: Path) -> list[Path]:
    candidates: list[Path] = []
    env_pwd = os.environ.get("PWD")
    if env_pwd:
        try:
            candidates.append(Path(env_pwd))
        except Exception:
            pass
    candidates.append(work_dir)
    try:
        candidates.append(work_dir.resolve())
    except Exception:
        pass
    return candidates


def candidate_project_paths(work_dir: Path) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for candidate in _candidate_paths(work_dir):
        normalized = normalize_project_path(candidate)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return out


def candidate_project_dirs(root: Path, work_dir: Path) -> list[Path]:
    return _candidate_project_dirs_impl(root, work_dir)


__all__ = ["candidate_project_dirs", "candidate_project_paths", "project_key_for_path"]
