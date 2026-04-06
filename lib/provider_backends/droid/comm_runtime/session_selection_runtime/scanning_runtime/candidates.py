from __future__ import annotations

import heapq
from pathlib import Path

from ...parsing import path_is_same_or_parent, read_droid_session_start


def top_recent_candidates(reader) -> list[Path]:
    heap: list[tuple[float, str]] = []
    for path in _iter_log_paths(reader):
        mtime = _read_mtime(path)
        if mtime is None:
            continue
        item = (mtime, str(path))
        if len(heap) < reader._scan_limit:
            heapq.heappush(heap, item)
        elif item[0] > heap[0][0]:
            heapq.heapreplace(heap, item)
    return [Path(path_str) for _, path_str in sorted(heap, key=lambda item: item[0], reverse=True)]


def latest_candidate_any_project(reader) -> Path | None:
    latest: Path | None = None
    latest_mtime = -1.0
    for path in _iter_log_paths(reader):
        mtime = _read_mtime(path)
        if mtime is None:
            continue
        if mtime >= latest_mtime:
            latest = path
            latest_mtime = mtime
    return latest


def matches_work_dir(path: Path, *, work_dir: Path) -> bool:
    cwd, _sid = read_droid_session_start(path)
    if not cwd:
        return False
    work_dir_str = str(work_dir)
    return path_is_same_or_parent(work_dir_str, cwd) or path_is_same_or_parent(cwd, work_dir_str)


def _iter_log_paths(reader):
    if not reader.root.exists():
        return
    try:
        for path in reader.root.glob("**/*.jsonl"):
            if not path.is_file() or path.name.startswith("."):
                continue
            yield path
    except Exception:
        return


def _read_mtime(path: Path) -> float | None:
    try:
        return path.stat().st_mtime
    except OSError:
        return None


__all__ = ["latest_candidate_any_project", "matches_work_dir", "top_recent_candidates"]
