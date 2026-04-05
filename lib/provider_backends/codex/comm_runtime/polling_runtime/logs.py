from __future__ import annotations

import time
from pathlib import Path

from ..session_selection import scan_latest


def ensure_log(reader, current_path: Path | None) -> Path:
    candidates = [
        reader._preferred_log if reader._preferred_log and reader._preferred_log.exists() else None,
        current_path if current_path and current_path.exists() else None,
    ]
    for candidate in candidates:
        if candidate:
            return candidate
    latest = scan_latest(reader)
    if latest:
        reader._preferred_log = latest
        return latest
    raise FileNotFoundError("Codex session log not found")


def maybe_switch_logs(
    reader,
    *,
    log_path: Path,
    current_path: Path | None,
    offset: int,
    last_rescan: float,
    rescan_interval: float,
) -> tuple[bool, Path | None, int, float]:
    if time.time() - last_rescan < rescan_interval:
        return False, current_path, offset, last_rescan

    latest = scan_latest(reader)
    if latest and latest != log_path:
        current_path = latest
        reader._preferred_log = latest
        return True, current_path, 0, time.time()
    return False, current_path, offset, time.time()


__all__ = ["ensure_log", "maybe_switch_logs"]
