from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .paths import OPENCODE_LOG_ROOT


def latest_opencode_log_file(root: Path = OPENCODE_LOG_ROOT) -> Path | None:
    try:
        if not root.exists():
            return None
        paths = [path for path in root.glob("*.log") if path.is_file()]
    except Exception:
        return None
    if not paths:
        return None
    try:
        paths.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    except Exception:
        paths.sort()
    return paths[0]


def is_cancel_log_line(line: str, *, session_id: str) -> bool:
    if not line:
        return False
    normalized_session_id = (session_id or "").strip()
    if not normalized_session_id:
        return False
    if f"sessionID={normalized_session_id} cancel" in line:
        return True
    if f"path=/session/{normalized_session_id}/abort" in line:
        return True
    return False


def parse_opencode_log_epoch_s(line: str) -> float | None:
    try:
        parts = (line or "").split()
        if len(parts) < 2:
            return None
        timestamp = parts[1]
        dt = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        return float(dt.timestamp())
    except Exception:
        return None
