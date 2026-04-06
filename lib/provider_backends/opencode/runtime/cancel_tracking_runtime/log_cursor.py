from __future__ import annotations

from pathlib import Path
from typing import Any

from opencode_runtime.logs import is_cancel_log_line, latest_opencode_log_file, parse_opencode_log_epoch_s


def open_cancel_log_cursor() -> dict[str, Any]:
    path = latest_opencode_log_file()
    if path is None:
        return {"path": None, "offset": 0}
    return _cursor_from_path(path, default_offset=True)


def detect_cancel_event_in_logs(
    cursor: dict[str, Any],
    *,
    session_id: str,
    since_epoch_s: float,
) -> tuple[bool, dict[str, Any]]:
    current_path, offset, cursor_mtime = _normalize_cursor(cursor)
    latest_path = latest_opencode_log_file()
    if latest_path is None:
        return False, {"path": None, "offset": 0, "mtime": 0.0}

    active_path, active_offset, active_mtime = _select_active_log_path(
        current_path=current_path,
        latest_path=latest_path,
        offset=offset,
        cursor_mtime=cursor_mtime,
    )
    size = _safe_stat_size(active_path)
    if size is None:
        return False, {"path": str(active_path), "offset": 0, "mtime": active_mtime}
    if active_offset < 0 or active_offset > size:
        active_offset = 0

    chunk = _read_log_chunk(active_path, offset=active_offset)
    new_cursor = _cursor_from_path(active_path, offset=size, fallback_mtime=active_mtime)
    if chunk is None or not chunk:
        return False, new_cursor

    for line in chunk.splitlines():
        if not is_cancel_log_line(line, session_id=session_id):
            continue
        ts = parse_opencode_log_epoch_s(line)
        if ts is None:
            continue
        if ts + 0.1 < float(since_epoch_s):
            continue
        return True, new_cursor
    return False, new_cursor


def _select_active_log_path(
    *,
    current_path: Path | None,
    latest_path: Path,
    offset: int,
    cursor_mtime: float,
) -> tuple[Path, int, float]:
    if current_path is None or not current_path.exists():
        return latest_path, 0, 0.0
    if latest_path == current_path:
        return current_path, offset, cursor_mtime
    latest_mtime = _safe_stat_mtime(latest_path) or 0.0
    if latest_mtime > cursor_mtime + 0.5:
        return latest_path, 0, 0.0
    return current_path, offset, cursor_mtime


def _normalize_cursor(cursor: dict[str, Any]) -> tuple[Path | None, int, float]:
    if not isinstance(cursor, dict):
        cursor = {}
    current_path = cursor.get("path")
    try:
        offset = int(cursor.get("offset") or 0)
    except Exception:
        offset = 0
    try:
        mtime = float(cursor.get("mtime") or 0.0)
    except Exception:
        mtime = 0.0
    path = Path(str(current_path)) if isinstance(current_path, str) and current_path else None
    return path, offset, mtime


def _read_log_chunk(path: Path, *, offset: int) -> str | None:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            handle.seek(offset)
            return handle.read()
    except Exception:
        return None


def _cursor_from_path(path: Path, *, default_offset: bool = False, offset: int | None = None, fallback_mtime: float = 0.0):
    size = _safe_stat_size(path) or 0
    mtime = _safe_stat_mtime(path)
    return {
        "path": str(path),
        "offset": size if default_offset else (offset if offset is not None else size),
        "mtime": mtime if mtime is not None else fallback_mtime,
    }


def _safe_stat_size(path: Path) -> int | None:
    try:
        return int(path.stat().st_size)
    except Exception:
        return None


def _safe_stat_mtime(path: Path) -> float | None:
    try:
        return float(path.stat().st_mtime)
    except Exception:
        return None


__all__ = ["detect_cancel_event_in_logs", "open_cancel_log_cursor"]
