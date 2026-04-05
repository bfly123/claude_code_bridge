from __future__ import annotations

import os
from pathlib import Path

from provider_core.runtime_specs import provider_marker_prefix


def initialize_state(
    comm,
    *,
    get_pane_id_from_session_fn,
    get_backend_for_session_fn,
) -> None:
    comm.session_info = comm._load_session_info()
    if not comm.session_info:
        raise RuntimeError("❌ No active Gemini session found, please run ccb gemini (or add gemini to ccb.config) first")

    comm.ccb_session_id = comm.session_info["ccb_session_id"]
    comm.runtime_dir = Path(comm.session_info["runtime_dir"])
    comm.terminal = comm.session_info.get("terminal", "tmux")
    comm.pane_id = get_pane_id_from_session_fn(comm.session_info)
    comm.pane_title_marker = comm.session_info.get("pane_title_marker") or ""
    comm.timeout = int(os.environ.get("GEMINI_SYNC_TIMEOUT", "60"))
    comm.marker_prefix = provider_marker_prefix("gemini")
    comm.project_session_file = comm.session_info.get("_session_file")
    comm.backend = get_backend_for_session_fn(comm.session_info)

    comm._log_reader = None
    comm._log_reader_primed = False


def ensure_log_reader(comm, *, log_reader_cls) -> None:
    if comm._log_reader is not None:
        return
    work_dir_hint = comm.session_info.get("work_dir")
    log_work_dir = Path(work_dir_hint) if isinstance(work_dir_hint, str) and work_dir_hint else None
    comm._log_reader = log_reader_cls(work_dir=log_work_dir)
    preferred_session = comm.session_info.get("gemini_session_path") or comm.session_info.get("session_path")
    if preferred_session:
        comm._log_reader.set_preferred_session(Path(str(preferred_session)))
    if not comm._log_reader_primed:
        comm._prime_log_binding()
        comm._log_reader_primed = True


def prime_log_binding(comm) -> None:
    session_path = comm.log_reader.current_session_path()
    if not session_path:
        return
    comm._remember_gemini_session(session_path)


__all__ = [
    "ensure_log_reader",
    "initialize_state",
    "prime_log_binding",
]
