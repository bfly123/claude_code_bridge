from __future__ import annotations

import json
from pathlib import Path

from ...registry_support.pathing import (
    candidate_project_dirs,
    project_key_for_path,
)


def session_belongs_to_current_project(reader, session_path: Path) -> bool:
    candidate = _resolved_existing_path(session_path)
    if candidate is None:
        return False
    return _candidate_parent_allowed(candidate.parent, allowed_dirs=_allowed_project_dirs(reader))


def project_dir(reader) -> Path:
    candidates = candidate_project_dirs(reader.root, reader.work_dir, include_env_pwd=False)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    if candidates:
        return candidates[-1]
    return reader.root / project_key_for_path(reader.work_dir)


def session_is_sidechain(session_path: Path) -> bool | None:
    entry = _first_json_entry(session_path, line_limit=20)
    if entry is None or 'isSidechain' not in entry:
        return None
    return bool(entry.get('isSidechain'))


def set_preferred_session(reader, session_path: Path | None) -> None:
    candidate = _resolved_existing_path(session_path)
    if candidate is None:
        return
    if session_belongs_to_current_project(reader, candidate):
        reader._preferred_session = candidate
        reader._preferred_session_locked = True


def _resolved_existing_path(pathlike: Path | str | None) -> Path | None:
    try:
        candidate = Path(pathlike).expanduser()
    except Exception:
        return None
    if not candidate.exists():
        return
    return _resolve_path(candidate)


def _allowed_project_dirs(reader) -> list[Path]:
    return [
        _resolve_path(project_dir)
        for project_dir in candidate_project_dirs(reader.root, reader.work_dir, include_env_pwd=False)
    ]


def _resolve_path(path: Path) -> Path:
    try:
        return path.resolve()
    except Exception:
        return path.absolute()


def _candidate_parent_allowed(candidate_parent: Path, *, allowed_dirs: list[Path]) -> bool:
    return any(candidate_parent == allowed_dir or allowed_dir in candidate_parent.parents for allowed_dir in allowed_dirs)


def _first_json_entry(session_path: Path, *, line_limit: int) -> dict | None:
    try:
        with session_path.open('r', encoding='utf-8', errors='replace') as handle:
            for _ in range(line_limit):
                entry = _json_line_entry(handle.readline())
                if entry is None:
                    continue
                return entry
    except OSError:
        return None
    return None


def _json_line_entry(line: str) -> dict | None:
    if not line:
        return None
    line = line.strip()
    if not line:
        return None
    try:
        entry = json.loads(line)
    except Exception:
        return None
    if isinstance(entry, dict):
        return entry
    return None


__all__ = [
    "project_dir",
    "session_belongs_to_current_project",
    "session_is_sidechain",
    "set_preferred_session",
]
