from __future__ import annotations

from typing import Any


def check_session_health(comm, *, probe_terminal: bool) -> tuple[bool, str]:
    try:
        if not comm.runtime_dir.exists():
            return False, "Runtime directory not found"
        if not comm.pane_id:
            return False, "Session ID not found"
        if probe_terminal and comm.backend:
            pane_alive = comm.backend.is_alive(comm.pane_id)
            if not pane_alive:
                return False, f"{comm.terminal} session {comm.pane_id} not found"
        return True, "Session OK"
    except Exception as exc:
        return False, f"Check failed: {exc}"


def get_status(comm) -> dict[str, Any]:
    healthy, status = comm._check_session_health()
    return {
        "ccb_session_id": comm.ccb_session_id,
        "runtime_dir": str(comm.runtime_dir),
        "terminal": comm.terminal,
        "pane_id": comm.pane_id,
        "healthy": healthy,
        "status": status,
    }


__all__ = ["check_session_health", "get_status"]
