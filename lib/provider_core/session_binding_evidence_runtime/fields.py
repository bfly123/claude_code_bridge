from __future__ import annotations

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
        return str(Path(session_log).expanduser())
    bound_session_file = session_file(session)
    if bound_session_file:
        return bound_session_file
    return None


def session_tmux_socket_name(session) -> str | None:
    terminal = str(getattr(session, 'terminal', '') or '').strip().lower()
    if terminal != 'tmux':
        return None
    data = getattr(session, 'data', None)
    if isinstance(data, dict):
        text = str(data.get('tmux_socket_name') or '').strip()
        if text:
            return text
    backend = session_backend(session)
    if backend is None:
        return None
    return str(getattr(backend, '_socket_name', '') or '').strip() or None


def session_tmux_socket_path(session) -> str | None:
    terminal = str(getattr(session, 'terminal', '') or '').strip().lower()
    if terminal != 'tmux':
        return None
    data = getattr(session, 'data', None)
    if isinstance(data, dict):
        text = str(data.get('tmux_socket_path') or '').strip()
        if text:
            return str(Path(text).expanduser())
    backend = session_backend(session)
    if backend is None:
        return None
    text = str(getattr(backend, '_socket_path', '') or '').strip()
    return str(Path(text).expanduser()) if text else None


def session_id(session, *, session_id_attr: str) -> str | None:
    value = getattr(session, session_id_attr, None)
    text = str(value or '').strip()
    return text or None


def session_file(session) -> str | None:
    session_path = getattr(session, 'session_file', None)
    if session_path is None:
        return None
    return str(Path(session_path).expanduser())


def session_runtime_root(session) -> str | None:
    runtime_dir = getattr(session, 'runtime_dir', None)
    if runtime_dir is not None:
        return str(Path(runtime_dir).expanduser())
    data = getattr(session, 'data', None)
    if isinstance(data, dict):
        text = str(data.get('runtime_dir') or '').strip()
        if text:
            return str(Path(text).expanduser())
    return None


def session_runtime_pid(session, *, provider: str) -> int | None:
    data = getattr(session, 'data', None)
    if isinstance(data, dict):
        for key in ('runtime_pid', 'pid'):
            value = coerce_pid(data.get(key))
            if value is not None:
                return value
    runtime_root = session_runtime_root(session)
    if not runtime_root:
        return None
    root = Path(runtime_root)
    preferred = root / f'{str(provider or "").strip().lower()}.pid'
    for candidate in (preferred, *sorted(root.glob('*.pid'))):
        value = read_pid_file(candidate)
        if value is not None:
            return value
    return None


def session_terminal(session) -> str | None:
    text = str(getattr(session, 'terminal', '') or '').strip()
    return text or None


def session_pane_title_marker(session) -> str | None:
    text = str(getattr(session, 'pane_title_marker', '') or '').strip()
    if text:
        return text
    data = getattr(session, 'data', None)
    if isinstance(data, dict):
        text = str(data.get('pane_title_marker') or '').strip()
        if text:
            return text
    return None


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


__all__ = [
    'session_file',
    'session_id',
    'session_pane_title_marker',
    'session_ref',
    'session_runtime_pid',
    'session_runtime_ref',
    'session_runtime_root',
    'session_terminal',
    'session_tmux_socket_name',
    'session_tmux_socket_path',
]
