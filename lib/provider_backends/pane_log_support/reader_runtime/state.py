from __future__ import annotations

from pathlib import Path
from typing import Any


def set_pane_log_path(reader, path: Path | None) -> None:
    if not path:
        return
    try:
        candidate = path if isinstance(path, Path) else Path(str(path)).expanduser()
    except Exception:
        return
    reader._pane_log_path = candidate


def resolve_log_path(reader) -> Path | None:
    if reader._pane_log_path and reader._pane_log_path.exists():
        return reader._pane_log_path
    return None


def capture_reader_state(reader) -> dict[str, Any]:
    log_path = resolve_log_path(reader)
    offset = 0
    if log_path and log_path.exists():
        try:
            offset = log_path.stat().st_size
        except OSError:
            offset = 0
    return {'pane_log_path': log_path, 'offset': offset}


__all__ = ["capture_reader_state", "resolve_log_path", "set_pane_log_path"]
