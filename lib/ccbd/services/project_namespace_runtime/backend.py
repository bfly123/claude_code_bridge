from __future__ import annotations

from dataclasses import dataclass
import os
import time
from typing import Callable


_PLACEHOLDER_CMD = 'while :; do sleep 3600; done'
_TMUX_OBJECT_READY_TIMEOUT_S = 3.0
_TMUX_OBJECT_READY_POLL_INTERVAL_S = 0.05


@dataclass(frozen=True)
class TmuxWindowRecord:
    window_id: str | None
    window_name: str
    active: bool = False


def build_backend(backend_factory, *, socket_path: str):
    try:
        return backend_factory(socket_path=socket_path)
    except TypeError:
        return backend_factory()


def prepare_server(backend) -> None:
    _tmux_run_ready(
        backend,
        ['start-server'],
        failure_message='failed to prepare tmux server',
    )


def ensure_server_policy(backend) -> None:
    _tmux_run_ready(
        backend,
        ['set-option', '-g', 'destroy-unattached', 'off'],
        failure_message='failed to persist tmux destroy-unattached policy',
    )


def create_session(backend, *, session_name: str, project_root, window_name: str | None = None) -> None:
    args = [
        'new-session',
        '-d',
        '-x',
        '160',
        '-y',
        '48',
        '-s',
        session_name,
    ]
    if str(window_name or '').strip():
        args.extend(['-n', str(window_name).strip()])
    args.extend(
        [
            '-c',
            str(project_root),
            'sh',
            '-lc',
            _PLACEHOLDER_CMD,
        ]
    )
    _tmux_run_ready(
        backend,
        args,
        failure_message=f'failed to create tmux session {session_name!r}',
    )


def session_window_target(session_name: str, window_name: str | None = None) -> str:
    session_text = str(session_name or '').strip()
    window_text = str(window_name or '').strip()
    if not session_text:
        raise ValueError('session_name cannot be empty')
    if not window_text:
        return session_text
    return f'{session_text}:{window_text}'


def list_windows(backend, session_name: str) -> tuple[TmuxWindowRecord, ...]:
    result = _tmux_run_ready(
        backend,
        ['list-windows', '-t', session_name, '-F', '#{window_id}\t#{window_name}\t#{window_active}'],
        failure_message=f'failed to list tmux windows for session {session_name!r}',
    )
    windows: list[TmuxWindowRecord] = []
    for line in (result.stdout or '').splitlines():
        parts = line.split('\t')
        if len(parts) != 3:
            continue
        window_id = (parts[0] or '').strip() or None
        window_name = (parts[1] or '').strip()
        if not window_name:
            continue
        windows.append(
            TmuxWindowRecord(
                window_id=window_id,
                window_name=window_name,
                active=(parts[2] or '').strip() in {'1', 'true', 'True'},
            )
        )
    return tuple(windows)


def find_window(backend, *, session_name: str, window_name: str) -> TmuxWindowRecord | None:
    target_name = str(window_name or '').strip()
    if not target_name:
        return None
    for record in list_windows(backend, session_name):
        if record.window_name == target_name:
            return record
    return None


def create_window(backend, *, session_name: str, window_name: str, project_root, select: bool = False) -> TmuxWindowRecord:
    _tmux_run_ready(
        backend,
        [
            'new-window',
            '-d',
            '-t',
            session_name,
            '-n',
            window_name,
            '-c',
            str(project_root),
            'sh',
            '-lc',
            _PLACEHOLDER_CMD,
        ],
        failure_message=f'failed to create tmux window {window_name!r} for session {session_name!r}',
    )
    record = wait_for_window(backend, session_name=session_name, window_name=window_name)
    if record is None:
        raise RuntimeError(f'failed to resolve tmux window {window_name!r} for session {session_name!r}')
    if select:
        select_window(
            backend,
            target=session_window_target(session_name, record.window_id or window_name),
        )
    return record


def ensure_window(backend, *, session_name: str, window_name: str, project_root, select: bool = False) -> TmuxWindowRecord:
    record = find_window(backend, session_name=session_name, window_name=window_name)
    if record is None:
        record = create_window(
            backend,
            session_name=session_name,
            window_name=window_name,
            project_root=project_root,
            select=select,
        )
    elif select:
        select_window(
            backend,
            target=session_window_target(session_name, record.window_id or window_name),
        )
    return record


def rename_window(backend, *, target: str, new_name: str) -> None:
    _tmux_run_ready(
        backend,
        ['rename-window', '-t', target, new_name],
        failure_message=f'failed to rename tmux window target {target!r} to {new_name!r}',
    )
    session_name, _sep, _old_name = target.partition(':')
    resolved_session_name = session_name.strip()
    if resolved_session_name and wait_for_window(backend, session_name=resolved_session_name, window_name=new_name) is None:
        raise RuntimeError(f'failed to observe renamed tmux window {new_name!r} for session {resolved_session_name!r}')


def kill_window(backend, *, target: str) -> None:
    _tmux_run_ready(
        backend,
        ['kill-window', '-t', target],
        failure_message=f'failed to kill tmux window target {target!r}',
    )


def session_alive(backend, session_name: str) -> bool:
    checker = getattr(backend, 'is_alive', None)
    if not callable(checker):
        return False
    try:
        return bool(checker(session_name))
    except Exception:
        return False


def session_root_pane(backend, session_name: str) -> str:
    return window_root_pane(backend, target_window=session_name)


def window_root_pane(backend, *, target_window: str) -> str:
    pane_id = wait_for_root_pane(backend, target_window=target_window)
    if not pane_id.startswith('%'):
        raise RuntimeError(f'failed to resolve root pane for tmux target {target_window!r}')
    return pane_id


def kill_server(backend) -> bool:
    try:
        backend._tmux_run(['kill-server'], check=False, capture=True)  # type: ignore[attr-defined]
        return True
    except Exception:
        return False


def wait_for_window(backend, *, session_name: str, window_name: str) -> TmuxWindowRecord | None:
    return _wait_until(
        lambda: find_window(backend, session_name=session_name, window_name=window_name),
    )


def select_window(backend, *, target: str) -> None:
    _wait_until_ready(
        lambda: _tmux_run_ready(
            backend,
            ['select-window', '-t', target],
            failure_message=f'failed to select tmux window target {target!r}',
            timeout_s=0.0,
        ),
        failure_message=f'failed to select tmux window target {target!r}',
    )


def wait_for_root_pane(backend, *, target_window: str) -> str:
    pane_id = _wait_until(
        lambda: _root_pane_once(backend, target_window=target_window),
    )
    if pane_id is None:
        raise RuntimeError(f'failed to resolve root pane for tmux target {target_window!r}')
    return pane_id


def _root_pane_once(backend, *, target_window: str) -> str | None:
    result = _tmux_run_once(
        backend,
        ['list-panes', '-t', target_window, '-F', '#{pane_id}'],
    )
    if result is None:
        return None
    pane_id = ((result.stdout or '').splitlines() or [''])[0].strip()
    return pane_id or None


def _tmux_run_ready(
    backend,
    args: list[str],
    *,
    failure_message: str,
    timeout_s: float | None = None,
):
    return _wait_until_ready(
        lambda: _tmux_run_checked(backend, args),
        failure_message=failure_message,
        timeout_s=timeout_s,
    )


def _tmux_run_once(backend, args: list[str]):
    try:
        return _tmux_run_checked(backend, args)
    except Exception:
        return None


def _tmux_run_checked(backend, args: list[str]):
    result = backend._tmux_run(args, check=False, capture=True)  # type: ignore[attr-defined]
    if int(getattr(result, 'returncode', 1) or 0) == 0:
        return result
    stdout = str(getattr(result, 'stdout', '') or '').strip()
    stderr = str(getattr(result, 'stderr', '') or '').strip()
    detail = stderr or stdout or f'tmux command failed: {" ".join(args)}'
    raise RuntimeError(detail)


def _wait_until(probe: Callable[[], object | None], *, timeout_s: float | None = None):
    deadline = time.monotonic() + _tmux_object_ready_timeout_s(timeout_s)
    while True:
        value = probe()
        if value is not None:
            return value
        if time.monotonic() >= deadline:
            return None
        time.sleep(_tmux_object_ready_poll_interval_s())


def _wait_until_ready(action: Callable[[], object], *, failure_message: str, timeout_s: float | None = None) -> object:
    deadline = time.monotonic() + _tmux_object_ready_timeout_s(timeout_s)
    last_error: Exception | None = None
    while True:
        try:
            return action()
        except Exception as exc:
            last_error = exc
        if time.monotonic() >= deadline:
            break
        time.sleep(_tmux_object_ready_poll_interval_s())
    if last_error is not None:
        raise RuntimeError(failure_message) from last_error
    raise RuntimeError(failure_message)


def _tmux_object_ready_timeout_s(timeout_s: float | None = None) -> float:
    if timeout_s is not None:
        return max(0.0, float(timeout_s))
    return _env_float('CCB_TMUX_OBJECT_READY_TIMEOUT_S', _TMUX_OBJECT_READY_TIMEOUT_S)


def _tmux_object_ready_poll_interval_s() -> float:
    return max(0.0, _env_float('CCB_TMUX_OBJECT_READY_POLL_INTERVAL_S', _TMUX_OBJECT_READY_POLL_INTERVAL_S))


def _env_float(name: str, default: float) -> float:
    raw = str(os.environ.get(name) or '').strip()
    if not raw:
        return default
    try:
        return float(raw)
    except Exception:
        return default


__all__ = [
    'build_backend',
    'create_session',
    'create_window',
    'ensure_server_policy',
    'ensure_window',
    'find_window',
    'kill_window',
    'kill_server',
    'list_windows',
    'prepare_server',
    'rename_window',
    'session_alive',
    'session_root_pane',
    'session_window_target',
    'select_window',
    'TmuxWindowRecord',
    'wait_for_root_pane',
    'wait_for_window',
    'window_root_pane',
]
