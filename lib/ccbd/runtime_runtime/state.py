from __future__ import annotations

import json
from pathlib import Path

from .files import state_file_path


def get_daemon_work_dir(state_file_name: str = "ccbd.json") -> Path | None:
    try:
        state_path = state_file_path(state_file_name)
        if not state_path.exists():
            return None
        with state_path.open("r", encoding="utf-8") as handle:
            state = json.load(handle)
        if not isinstance(state, dict):
            return None
        work_dir = state.get("work_dir")
        if not work_dir or not isinstance(work_dir, str):
            return None
        return Path(work_dir.strip())
    except Exception:
        return None


__all__ = ["get_daemon_work_dir"]
