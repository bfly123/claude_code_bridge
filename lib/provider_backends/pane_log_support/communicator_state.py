from __future__ import annotations

import os
from pathlib import Path


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
    comm.timeout = int(os.environ.get(comm.sync_timeout_env, os.environ.get('CCB_SYNC_TIMEOUT', '3600')))
    comm.project_session_file = comm.session_info.get('_session_file')
    comm._log_reader = None
    comm._log_reader_primed = False


def ensure_log_reader(comm, *, reader_cls) -> None:
    if comm._log_reader is not None:
        return
    comm._log_reader = reader_cls(
        work_dir=_work_dir_hint(comm.session_info),
        pane_log_path=_pane_log_path(comm.session_info),
    )
    comm._log_reader_primed = True


def _required_session_info(comm):
    session_info = comm._load_session_info()
    if session_info:
        return session_info
    raise RuntimeError(comm.missing_session_message)


def _work_dir_hint(session_info: dict) -> Path | None:
    work_dir = session_info.get('work_dir')
    return Path(work_dir) if isinstance(work_dir, str) and work_dir else None


def _pane_log_path(session_info: dict) -> Path | None:
    raw_log_path = session_info.get('pane_log_path')
    if raw_log_path:
        return Path(str(raw_log_path)).expanduser()
    runtime_dir = session_info.get('runtime_dir')
    if runtime_dir:
        return Path(str(runtime_dir)) / 'pane.log'
    return None


__all__ = ['ensure_log_reader', 'initialize_state']
