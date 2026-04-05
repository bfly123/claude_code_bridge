from __future__ import annotations

import os
from typing import Any

from .session_selection import latest_log


def capture_log_reader_state(reader) -> dict[str, Any]:
    log = latest_log(reader)
    offset = -1
    if log and log.exists():
        try:
            offset = log.stat().st_size
        except OSError:
            try:
                with log.open("rb") as handle:
                    handle.seek(0, os.SEEK_END)
                    offset = handle.tell()
            except OSError:
                offset = -1
    return {"log_path": log, "offset": offset}


__all__ = ["capture_log_reader_state"]
