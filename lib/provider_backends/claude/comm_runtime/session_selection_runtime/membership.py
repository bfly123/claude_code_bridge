from __future__ import annotations

import json
from pathlib import Path

from ...registry_support.pathing import (
    candidate_project_dirs,
    project_key_for_path,
)

# Transcript preambles can push the first `isSidechain` far past a small
# fixed line window. Skip these record types so the probe budget is spent on
# entries that can actually carry membership.
_SIDECHAIN_PROBE_SKIP_TYPES = frozenset(
    {
        'file-history-snapshot',
        'ai-title',
        'agent-name',
        'mode',
        'permission-mode',
        'summary',
    }
)
_SIDECHAIN_PROBE_CANDIDATE_LIMIT = 40
_SIDECHAIN_PROBE_ABSOLUTE_LINE_LIMIT = 2000


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
    entry = _first_json_entry_with_key(
        session_path,
        key='isSidechain',
        candidate_limit=_SIDECHAIN_PROBE_CANDIDATE_LIMIT,
        absolute_line_limit=_SIDECHAIN_PROBE_ABSOLUTE_LINE_LIMIT,
    )
    if entry is None:
        return None
    return bool(entry.get('isSidechain'))


def set_preferred_session(reader, session_path: Path | None) -> None:
    candidate = _resolved_existing_path(session_path)
    if candidate is None:
        return
    if session_belongs_to_current_project(reader, candidate):
        reader._preferred_session = candidate
        reader._preferred_session_locked = True


def allow_preferred_session_rotation(reader) -> None:
    """Allow a bound Claude pane to move to a newer same-project session."""
    reader._preferred_session_locked = False


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


def _first_json_entry_with_key(
    session_path: Path,
    *,
    key: str,
    candidate_limit: int,
    absolute_line_limit: int,
) -> dict | None:
    try:
        with session_path.open('r', encoding='utf-8', errors='replace') as handle:
            candidates_seen = 0
            for _ in range(max(0, int(absolute_line_limit))):
                entry = _json_line_entry(handle.readline())
                if entry is None:
                    continue
                entry_type = str(entry.get('type') or '').strip()
                if entry_type in _SIDECHAIN_PROBE_SKIP_TYPES:
                    continue
                candidates_seen += 1
                if key in entry:
                    return entry
                if candidates_seen >= max(1, int(candidate_limit)):
                    break
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
    "allow_preferred_session_rotation",
    "session_belongs_to_current_project",
    "session_is_sidechain",
    "set_preferred_session",
]
