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
    comm.session_info = _required_session_info(comm)
    comm.ccb_session_id = str(comm.session_info.get('ccb_session_id') or '').strip()
    comm.terminal = comm.session_info.get('terminal', 'tmux')
    comm.pane_id = get_pane_id_from_session_fn(comm.session_info) or ''
    comm.pane_title_marker = comm.session_info.get('pane_title_marker') or ''
    comm.backend = get_backend_for_session_fn(comm.session_info)
    comm.timeout = int(os.environ.get('DROID_SYNC_TIMEOUT', os.environ.get('CCB_SYNC_TIMEOUT', '3600')))
    comm.marker_prefix = provider_marker_prefix('droid')
    comm.project_session_file = comm.session_info.get('_session_file')
    comm._log_reader = None
    comm._log_reader_primed = False


def ensure_log_reader(comm, *, log_reader_cls) -> None:
    if comm._log_reader is not None:
        return
    comm._log_reader = log_reader_cls(work_dir=_work_dir_hint(comm.session_info))
    preferred_session = comm.session_info.get('droid_session_path')
    if preferred_session:
        comm._log_reader.set_preferred_session(Path(str(preferred_session)))
    session_id = comm.session_info.get('droid_session_id')
    if session_id:
        comm._log_reader.set_session_id_hint(session_id)
    if comm._log_reader_primed:
        return
    comm._prime_log_binding()
    comm._log_reader_primed = True


def _required_session_info(comm):
    session_info = comm._load_session_info()
    if session_info:
        return session_info
    raise RuntimeError("❌ No active Droid session found. Run 'ccb droid' (or add droid to ccb.config) first")


def _work_dir_hint(session_info: dict) -> Path | None:
    work_dir = session_info.get('work_dir')
    return Path(work_dir) if isinstance(work_dir, str) and work_dir else None


__all__ = ['ensure_log_reader', 'initialize_state']
