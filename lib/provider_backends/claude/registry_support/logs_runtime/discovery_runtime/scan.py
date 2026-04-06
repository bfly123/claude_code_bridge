from __future__ import annotations

import heapq
from pathlib import Path

from ...pathing import path_within
from ..meta import read_session_meta


def scan_latest_log_for_work_dir(work_dir: Path, *, root: Path, scan_limit: int) -> tuple[Path | None, str | None]:
    root = Path(root).expanduser()
    if not root.exists():
        return None, None
    candidates = _candidate_logs(root, scan_limit=scan_limit)
    work_dir_str = str(work_dir)
    for candidate in candidates:
        cwd, sid, is_sidechain = read_session_meta(candidate)
        if is_sidechain is True or not cwd:
            continue
        if path_within(cwd, work_dir_str):
            return candidate, sid
    return None, None


def _candidate_logs(root: Path, *, scan_limit: int) -> list[Path]:
    heap: list[tuple[float, str]] = []
    try:
        for path in root.glob('**/*.jsonl'):
            if not path.is_file() or path.name.startswith('.'):
                continue
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            item = (mtime, str(path))
            if len(heap) < scan_limit:
                heapq.heappush(heap, item)
            elif item[0] > heap[0][0]:
                heapq.heapreplace(heap, item)
    except Exception:
        return []
    return [Path(path_str) for _, path_str in sorted(heap, key=lambda item: item[0], reverse=True)]


__all__ = ['scan_latest_log_for_work_dir']
