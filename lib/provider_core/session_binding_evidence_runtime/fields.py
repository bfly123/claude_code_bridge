from __future__ import annotations

import os
from pathlib import Path

from .backend import session_backend


def session_runtime_ref(session, *, pane_id_override: str | None = None) -> str | None:
    pane_id = str(pane_id_override or getattr(session, 'pane_id', '') or '').strip()
    terminal = str(getattr(session, 'terminal', '') or '').strip() or 'tmux'
    if pane_id:
        return f'{terminal}:{pane_id}'
    return None


def session_ref(session, *, session_id_attr: str, session_path_attr: str) -> str | None:
    session_token = str(getattr(session, session_id_attr, '') or '').strip()
    if session_token:
        return session_token
    session_log = str(getattr(session, session_path_attr, '') or '').strip()
    if session_log:
        return os.path.expanduser(session_log)
    bound_session_file = session_file(session)
    if bound_session_file:
        return bound_session_file
    return None


def session_tmux_socket_name(session) -> str | None:
    if not _session_uses_tmux(session):
        return None
    return _session_data_text(session, 'tmux_socket_name') or _backend_text(session, '_socket_name')


def session_tmux_socket_path(session) -> str | None:
    if not _session_uses_tmux(session):
        return None
    text = _session_data_text(session, 'tmux_socket_path') or _backend_text(session, '_socket_path')
    return _expanded_path_text(text)


def session_id(session, *, session_id_attr: str) -> str | None:
    value = getattr(session, session_id_attr, None)
    text = str(value or '').strip()
    return text or None


def session_file(session) -> str | None:
    session_path = getattr(session, 'session_file', None)
    if session_path is None:
        return None
    return os.path.expanduser(str(session_path))


def session_runtime_root(session) -> str | None:
    runtime_dir = getattr(session, 'runtime_dir', None)
    if runtime_dir is not None:
        return os.path.expanduser(str(runtime_dir))
    data = getattr(session, 'data', None)
    if isinstance(data, dict):
        text = str(data.get('runtime_dir') or '').strip()
        if text:
            return os.path.expanduser(text)
    return None


def session_runtime_pid(session, *, provider: str) -> int | None:
    direct_pid = _session_data_pid(session)
    if direct_pid is not None:
        return direct_pid
    runtime_root = _runtime_root_path(session)
    if runtime_root is None:
        return None
    for candidate in _pid_file_candidates(runtime_root, provider=provider):
        value = read_pid_file(candidate)
        if value is not None:
            return value
    return None


def session_terminal(session) -> str | None:
    text = str(getattr(session, 'terminal', '') or '').strip()
    return text or None


def session_job_id(session) -> str | None:
    text = str(getattr(session, 'job_id', '') or '').strip()
    if text:
        return text
    from_data = _session_data_text(session, 'job_id')
    if from_data:
        return from_data
    runtime_root = _runtime_root_path(session)
    if runtime_root is None:
        return None
    for candidate in _job_id_file_candidates(runtime_root):
        value = read_text_file(candidate)
        if value is not None:
            return value
    return None


def session_job_owner_pid(session) -> int | None:
    direct = coerce_pid(getattr(session, 'job_owner_pid', None))
    if direct is not None:
        return direct
    data = _session_data(session)
    if data is not None:
        from_data = coerce_pid(data.get('job_owner_pid'))
        if from_data is not None:
            return from_data
    runtime_root = _runtime_root_path(session)
    if runtime_root is None:
        return None
    for candidate in _job_owner_pid_file_candidates(runtime_root):
        value = read_pid_file(candidate)
        if value is not None:
            return value
    return None


def session_pane_title_marker(session) -> str | None:
    text = str(getattr(session, 'pane_title_marker', '') or '').strip()
    if text:
        return text
    return _session_data_text(session, 'pane_title_marker')


def _session_uses_tmux(session) -> bool:
    return str(getattr(session, 'terminal', '') or '').strip().lower() in {'tmux', 'psmux'}


def _session_data(session) -> dict | None:
    data = getattr(session, 'data', None)
    if isinstance(data, dict):
        return data
    return None


def _session_data_text(session, key: str) -> str | None:
    data = _session_data(session)
    if data is None:
        return None
    text = str(data.get(key) or '').strip()
    return text or None


def _backend_text(session, attr_name: str) -> str | None:
    backend = session_backend(session)
    if backend is None:
        return None
    text = str(getattr(backend, attr_name, '') or '').strip()
    return text or None


def _expanded_path_text(text: str | None) -> str | None:
    if not text:
        return None
    return os.path.expanduser(text)


def _session_data_pid(session) -> int | None:
    data = _session_data(session)
    if data is None:
        return None
    for key in ('runtime_pid', 'pid'):
        value = coerce_pid(data.get(key))
        if value is not None:
            return value
    return None


def _runtime_root_path(session) -> Path | None:
    runtime_root = session_runtime_root(session)
    if not runtime_root:
        return None
    return Path(runtime_root)


def _pid_file_candidates(runtime_root: Path, *, provider: str) -> tuple[Path, ...]:
    provider_name = str(provider or '').strip().lower()
    preferred = runtime_root / f'{provider_name}.pid'
    return (preferred, *sorted(runtime_root.glob('*.pid')))


def _job_owner_pid_file_candidates(runtime_root: Path) -> tuple[Path, ...]:
    return (
        runtime_root / 'job-owner.pid',
        runtime_root / 'owner.pid',
        runtime_root / 'bridge.pid',
    )


def _job_id_file_candidates(runtime_root: Path) -> tuple[Path, ...]:
    return (runtime_root / 'job.id',)


def coerce_pid(value: object) -> int | None:
    text = str(value or '').strip()
    if not text.isdigit():
        return None
    pid = int(text)
    return pid if pid > 0 else None


def read_pid_file(path: Path) -> int | None:
    if not path.is_file():
        return None
    try:
        return coerce_pid(path.read_text(encoding='utf-8'))
    except Exception:
        return None


def read_text_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding='utf-8').strip()
    except Exception:
        return None
    return text or None


__all__ = [
    'session_file',
    'session_id',
    'session_job_id',
    'session_job_owner_pid',
    'session_pane_title_marker',
    'session_ref',
    'session_runtime_pid',
    'session_runtime_ref',
    'session_runtime_root',
    'session_terminal',
    'session_tmux_socket_name',
    'session_tmux_socket_path',
]
