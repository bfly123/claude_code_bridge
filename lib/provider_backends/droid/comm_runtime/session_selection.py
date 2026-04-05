from __future__ import annotations

import heapq
import os
from pathlib import Path

from .parsing import path_is_same_or_parent, read_droid_session_start


def set_preferred_session(reader, session_path: Path | None) -> None:
    if not session_path:
        return
    try:
        candidate = session_path if isinstance(session_path, Path) else Path(str(session_path)).expanduser()
    except Exception:
        return
    if candidate.exists():
        reader._preferred_session = candidate


def set_session_id_hint(reader, session_id: str | None) -> None:
    if not session_id:
        return
    reader._session_id_hint = str(session_id).strip()


def find_session_by_id(reader) -> Path | None:
    session_id = (reader._session_id_hint or "").strip()
    if not session_id or not reader.root.exists():
        return None
    latest: Path | None = None
    latest_mtime = -1.0
    try:
        for path in reader.root.glob(f"**/{session_id}.jsonl"):
            if not path.is_file():
                continue
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            if mtime >= latest_mtime:
                latest_mtime = mtime
                latest = path
    except Exception:
        return None
    return latest


def scan_latest_session(reader) -> Path | None:
    if not reader.root.exists():
        return None
    heap: list[tuple[float, str]] = []
    try:
        for path in reader.root.glob("**/*.jsonl"):
            if not path.is_file() or path.name.startswith("."):
                continue
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            item = (mtime, str(path))
            if len(heap) < reader._scan_limit:
                heapq.heappush(heap, item)
            elif item[0] > heap[0][0]:
                heapq.heapreplace(heap, item)
    except Exception:
        return None

    candidates = sorted(heap, key=lambda item: item[0], reverse=True)
    work_dir_str = str(reader.work_dir)
    for _, path_str in candidates:
        path = Path(path_str)
        cwd, _sid = read_droid_session_start(path)
        if not cwd:
            continue
        if path_is_same_or_parent(work_dir_str, cwd) or path_is_same_or_parent(cwd, work_dir_str):
            return path
    return None


def scan_latest_session_any_project(reader) -> Path | None:
    if not reader.root.exists():
        return None
    latest: Path | None = None
    latest_mtime = -1.0
    try:
        for path in reader.root.glob("**/*.jsonl"):
            if not path.is_file() or path.name.startswith("."):
                continue
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            if mtime >= latest_mtime:
                latest_mtime = mtime
                latest = path
    except Exception:
        return None
    return latest


def latest_session(reader) -> Path | None:
    preferred = reader._preferred_session
    scanned = scan_latest_session(reader)

    if preferred and preferred.exists():
        if scanned and scanned.exists():
            try:
                pref_mtime = preferred.stat().st_mtime
                scan_mtime = scanned.stat().st_mtime
                if scan_mtime > pref_mtime:
                    reader._preferred_session = scanned
                    return scanned
            except OSError:
                pass
        return preferred

    by_id = find_session_by_id(reader)
    if by_id:
        reader._preferred_session = by_id
        return by_id

    if scanned:
        reader._preferred_session = scanned
        return scanned

    if os.environ.get("DROID_ALLOW_ANY_PROJECT_SCAN") in ("1", "true", "yes"):
        any_latest = scan_latest_session_any_project(reader)
        if any_latest:
            reader._preferred_session = any_latest
            return any_latest
    return None


__all__ = [
    "find_session_by_id",
    "latest_session",
    "scan_latest_session",
    "scan_latest_session_any_project",
    "set_preferred_session",
    "set_session_id_hint",
]
