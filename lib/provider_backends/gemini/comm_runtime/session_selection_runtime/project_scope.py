from __future__ import annotations

from pathlib import Path

from ..project_hash import project_root_marker


def session_belongs_to_current_project(reader, session_path: Path) -> bool:
    candidate = _coerce_existing_session_path(session_path)
    if candidate is None:
        return False
    if candidate.parent.name != "chats":
        return False

    project_dir = candidate.parent.parent
    project_hash = (project_dir.name or "").strip()
    if not project_hash:
        return False
    if project_dir.parent != _resolve_root(reader.root):
        return False

    marker = project_root_marker(project_dir)
    if marker and marker != reader._work_dir_norm:
        return False
    return project_hash == reader._project_hash or project_hash in reader._all_known_hashes


def adopt_project_hash_from_session(reader, session_path: Path) -> None:
    project_hash = _project_hash_from_session_path(session_path)
    if not project_hash:
        return
    reader._project_hash = project_hash
    reader._all_known_hashes.add(project_hash)


def _coerce_existing_session_path(session_path: Path | str | None) -> Path | None:
    if not session_path:
        return None
    try:
        candidate = session_path if isinstance(session_path, Path) else Path(str(session_path)).expanduser()
    except Exception:
        return None
    if not candidate.exists():
        return None
    return _resolve_root(candidate)


def _project_hash_from_session_path(session_path: Path) -> str:
    try:
        candidate = _resolve_root(session_path)
    except Exception:
        return ""
    if candidate.parent.name != "chats":
        return ""
    return (candidate.parent.parent.name or "").strip()


def _resolve_root(path: Path) -> Path:
    try:
        return path.resolve()
    except Exception:
        return path.absolute()


__all__ = [
    "adopt_project_hash_from_session",
    "session_belongs_to_current_project",
]
