from __future__ import annotations

import heapq
import re
from pathlib import Path

from ..pathing import path_within
from .meta import read_session_meta


SESSION_ID_PATTERN = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)


def extract_session_id_from_start_cmd(start_cmd: str) -> str | None:
    if not start_cmd:
        return None
    match = SESSION_ID_PATTERN.search(start_cmd)
    if not match:
        return None
    return match.group(0)


def find_log_for_session_id(session_id: str, *, root: Path) -> Path | None:
    root = Path(root).expanduser()
    if not session_id or not root.exists():
        return None
    latest: Path | None = None
    latest_mtime = -1.0
    try:
        patterns = [f"**/{session_id}.jsonl", f"**/*{session_id}*.jsonl"]
        seen: set[str] = set()
        for pattern in patterns:
            for path in root.glob(pattern):
                if not path.is_file():
                    continue
                path_str = str(path)
                if path_str in seen:
                    continue
                seen.add(path_str)
                try:
                    mtime = path.stat().st_mtime
                except OSError:
                    continue
                if mtime >= latest_mtime:
                    latest = path
                    latest_mtime = mtime
    except Exception:
        return None
    return latest


def scan_latest_log_for_work_dir(work_dir: Path, *, root: Path, scan_limit: int) -> tuple[Path | None, str | None]:
    root = Path(root).expanduser()
    if not root.exists():
        return None, None

    work_dir_str = str(work_dir)
    heap: list[tuple[float, str]] = []
    try:
        for path in root.glob("**/*.jsonl"):
            if not path.is_file() or path.name.startswith("."):
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
        return None, None

    candidates = sorted(heap, key=lambda item: item[0], reverse=True)
    for _, path_str in candidates:
        path = Path(path_str)
        cwd, sid, is_sidechain = read_session_meta(path)
        if is_sidechain is True or not cwd:
            continue
        if path_within(cwd, work_dir_str):
            return path, sid
    return None, None


__all__ = [
    "extract_session_id_from_start_cmd",
    "find_log_for_session_id",
    "scan_latest_log_for_work_dir",
]
