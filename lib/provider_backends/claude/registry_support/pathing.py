from __future__ import annotations

from pathlib import Path

from provider_backends.claude.resolver_runtime.pathing import project_key_for_path
from provider_backends.claude.session_runtime.pathing import (
    ensure_work_dir_fields as _ensure_work_dir_fields,
    infer_work_dir_from_session_file,
)

from .pathing_runtime import candidate_project_dirs, candidate_project_paths, normalize_project_path, path_within


def ensure_claude_session_work_dir_fields(payload: dict, session_file: Path) -> Path | None:
    return _ensure_work_dir_fields(payload, session_file=session_file)


__all__ = [
    "candidate_project_dirs",
    "candidate_project_paths",
    "ensure_claude_session_work_dir_fields",
    "infer_work_dir_from_session_file",
    "normalize_project_path",
    "path_within",
    "project_key_for_path",
]
