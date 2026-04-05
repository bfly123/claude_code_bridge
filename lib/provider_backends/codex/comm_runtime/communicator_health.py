from __future__ import annotations

import time
from typing import Any


def check_session_health(comm, *, probe_terminal: bool, tmux_health_checker):
    try:
        if not comm.runtime_dir.exists():
            return False, "Runtime directory does not exist"
        return tmux_health_checker(runtime_dir=comm.runtime_dir, input_fifo=comm.input_fifo)
    except Exception as exc:
        return False, f"Health check failed: {exc}"


def pane_alive(comm, *, force: bool) -> bool:
    ttl = comm._pane_health_ttl
    now = time.time()
    if (not force) and ttl > 0 and comm._pane_health_cache:
        cached_ts, cached_val = comm._pane_health_cache
        if now - cached_ts < ttl:
            return cached_val
    backend = comm.backend
    pane_id = comm.pane_id
    alive = bool(backend and pane_id and backend.is_alive(pane_id))
    if ttl > 0:
        comm._pane_health_cache = (now, alive)
    else:
        comm._pane_health_cache = None
    return alive


def get_status(comm) -> dict[str, Any]:
    healthy, status = comm._check_session_health()
    info = {
        "ccb_session_id": comm.ccb_session_id,
        "runtime_dir": str(comm.runtime_dir),
        "healthy": healthy,
        "status": status,
        "input_fifo": str(comm.input_fifo),
    }

    codex_pid_file = comm.runtime_dir / "codex.pid"
    if codex_pid_file.exists():
        with open(codex_pid_file, "r", encoding="utf-8") as handle:
            info["codex_pid"] = int(handle.read().strip())

    return info


__all__ = ["check_session_health", "get_status", "pane_alive"]
