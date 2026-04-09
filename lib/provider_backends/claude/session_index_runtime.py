from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .registry_support.pathing import candidate_project_paths, normalize_project_path, project_key_for_path


@dataclass(frozen=True)
class SessionIndexLocation:
    index_path: Path
    project_dir: Path


def candidate_paths_for_work_dir(work_dir: Path, *, include_env_pwd: bool = True) -> set[str]:
    return set(candidate_project_paths(work_dir, include_env_pwd=include_env_pwd))


def resolve_registry_index_location(work_dir: Path, *, root: Path) -> SessionIndexLocation | None:
    location = project_index_location(root=root, project_dir=root / project_key_for_path(work_dir))
    if location is not None:
        return location

    try:
        resolved = work_dir.resolve()
    except Exception:
        resolved = work_dir
    if resolved == work_dir:
        return None
    return project_index_location(root=root, project_dir=root / project_key_for_path(resolved))


def project_index_location(*, root: Path, project_dir: Path) -> SessionIndexLocation | None:
    del root
    index_path = project_dir / "sessions-index.json"
    if not index_path.exists():
        return None
    return SessionIndexLocation(index_path=index_path, project_dir=project_dir)


def load_index_entries(index_path: Path) -> list[dict[str, object]] | None:
    try:
        payload = json.loads(index_path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None
    entries = payload.get("entries") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        return None
    return [entry for entry in entries if isinstance(entry, dict)]


def select_best_session_path(
    entries: list[dict[str, object]],
    *,
    candidates: set[str],
    project_dir: Path,
    session_filter: Callable[[Path], bool] | None = None,
) -> Path | None:
    best_path: Path | None = None
    best_mtime = -1
    for entry in entries:
        candidate = entry_session_path(
            entry,
            candidates=candidates,
            project_dir=project_dir,
            session_filter=session_filter,
        )
        if candidate is None:
            continue
        session_path, mtime = candidate
        if mtime > best_mtime:
            best_mtime = mtime
            best_path = session_path
    return best_path


def entry_session_path(
    entry: dict[str, object],
    *,
    candidates: set[str],
    project_dir: Path,
    session_filter: Callable[[Path], bool] | None = None,
) -> tuple[Path, int] | None:
    if entry.get("isSidechain") is True:
        return None
    if not entry_matches_candidates(entry, candidates):
        return None
    session_path = resolve_session_path(entry, project_dir=project_dir)
    if session_path is None:
        return None
    if session_filter is not None and not session_filter(session_path):
        return None
    mtime = entry_mtime(entry, session_path)
    if mtime is None:
        return None
    return session_path, mtime


def entry_matches_candidates(entry: dict[str, object], candidates: set[str]) -> bool:
    project_path = entry.get("projectPath")
    if isinstance(project_path, str) and project_path.strip():
        normalized = normalize_project_path(project_path)
        return not candidates or not normalized or normalized in candidates
    return not candidates


def resolve_session_path(entry: dict[str, object], *, project_dir: Path) -> Path | None:
    full_path = entry.get("fullPath")
    if not isinstance(full_path, str) or not full_path.strip():
        return None
    try:
        session_path = Path(full_path).expanduser()
    except Exception:
        return None
    if not session_path.is_absolute():
        session_path = (project_dir / session_path).expanduser()
    if not session_path.exists():
        return None
    return session_path


def entry_mtime(entry: dict[str, object], session_path: Path) -> int | None:
    mtime_raw = entry.get("fileMtime")
    if isinstance(mtime_raw, (int, float)):
        return int(mtime_raw)
    if isinstance(mtime_raw, str) and mtime_raw.strip().isdigit():
        try:
            return int(mtime_raw.strip())
        except Exception:
            return None
    try:
        return int(session_path.stat().st_mtime * 1000)
    except OSError:
        return None


__all__ = [
    "candidate_paths_for_work_dir",
    "entry_mtime",
    "load_index_entries",
    "project_index_location",
    "resolve_registry_index_location",
    "select_best_session_path",
]
