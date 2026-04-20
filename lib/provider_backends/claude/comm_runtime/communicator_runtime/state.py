from __future__ import annotations

import os
from pathlib import Path

from provider_core.runtime_specs import provider_marker_prefix


def initialize_state(
    comm,
    *,
    get_backend_for_session_fn,
    get_pane_id_from_session_fn,
) -> None:
    comm.session_info = comm._load_session_info()
    if not comm.session_info:
        raise RuntimeError("❌ No active Claude session found. Run 'ccb claude' (or add claude to ccb.config) first")

    comm.session_id = str(comm.session_info.get("claude_session_id") or "").strip()
    comm.terminal = comm.session_info.get("terminal", "tmux")
    comm.pane_id = get_pane_id_from_session_fn(comm.session_info) or ""
    comm.pane_title_marker = comm.session_info.get("pane_title_marker") or ""
    comm.backend = get_backend_for_session_fn(comm.session_info)
    comm.timeout = int(os.environ.get("CLAUDE_SYNC_TIMEOUT", os.environ.get("CCB_SYNC_TIMEOUT", "3600")))
    comm.marker_prefix = provider_marker_prefix("claude")
    comm.project_session_file = comm.session_info.get("_session_file")

    comm._log_reader = None
    comm._log_reader_primed = False


def check_session_health(comm, *, probe_terminal: bool) -> tuple[bool, str]:
    try:
        if not comm.pane_id:
            return False, "Session pane id not found"
        if probe_terminal and comm.backend:
            pane_alive = comm.backend.is_alive(comm.pane_id)
            if not pane_alive:
                return False, f"{comm.terminal} session {comm.pane_id} not found"
        return True, "Session OK"
    except Exception as exc:
        return False, f"Check failed: {exc}"


__all__ = ["check_session_health", "initialize_state"]
