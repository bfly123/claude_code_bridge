from __future__ import annotations

import json
from pathlib import Path

from ...registry_support.pathing import (
    candidate_project_dirs,
    project_key_for_path,
)


def session_belongs_to_current_project(reader, session_path: Path) -> bool:
    try:
        candidate = Path(session_path).expanduser()
    except Exception:
        return False
    if not candidate.exists():
        return False
    try:
        resolved_candidate = candidate.resolve()
    except Exception:
        resolved_candidate = candidate.absolute()

    allowed_dirs: list[Path] = []
    for project_dir in candidate_project_dirs(reader.root, reader.work_dir):
        try:
            allowed_dirs.append(project_dir.resolve())
        except Exception:
            allowed_dirs.append(project_dir.absolute())

    candidate_parent = resolved_candidate.parent
    for allowed_dir in allowed_dirs:
        if candidate_parent == allowed_dir or allowed_dir in candidate_parent.parents:
            return True
    return False


def project_dir(reader) -> Path:
    candidates = candidate_project_dirs(reader.root, reader.work_dir)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    if candidates:
        return candidates[-1]
    return reader.root / project_key_for_path(reader.work_dir)


def session_is_sidechain(session_path: Path) -> bool | None:
    try:
        with session_path.open("r", encoding="utf-8", errors="replace") as handle:
            for _ in range(20):
                line = handle.readline()
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except Exception:
                    continue
                if isinstance(entry, dict) and "isSidechain" in entry:
                    return bool(entry.get("isSidechain"))
    except OSError:
        return None
    return None


def set_preferred_session(reader, session_path: Path | None) -> None:
    if not session_path:
        return
    try:
        candidate = session_path if isinstance(session_path, Path) else Path(str(session_path)).expanduser()
    except Exception:
        return
    if candidate.exists() and session_belongs_to_current_project(reader, candidate):
        reader._preferred_session = candidate


__all__ = [
    "project_dir",
    "session_belongs_to_current_project",
    "session_is_sidechain",
    "set_preferred_session",
]
