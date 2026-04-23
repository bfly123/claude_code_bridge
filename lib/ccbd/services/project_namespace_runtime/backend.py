from __future__ import annotations

from dataclasses import dataclass
import os


_PLACEHOLDER_CMD = 'while :; do sleep 3600; done'
_PLACEHOLDER_CMD_WINDOWS = 'ping -t 127.0.0.1 >nul'


def _placeholder_spawn_args(backend) -> list[str]:
    backend_impl = str(getattr(backend, 'backend_impl', '') or '').strip().lower()
    if os.name == 'nt' and backend_impl == 'psmux':
        return ['cmd.exe', '/d', '/s', '/c', _PLACEHOLDER_CMD_WINDOWS]
    return ['sh', '-lc', _PLACEHOLDER_CMD]


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
    backend._tmux_run(['start-server'], check=False, capture=True)  # type: ignore[attr-defined]
    backend._tmux_run(['set-option', '-g', 'destroy-unattached', 'off'], check=False, capture=True)  # type: ignore[attr-defined]


def _enable_placeholder_remain_on_exit(backend, *, pane_id: str) -> None:
    backend_impl = str(getattr(backend, 'backend_impl', '') or '').strip().lower()
    if os.name != 'nt' or backend_impl != 'psmux':
        return
    pane_text = str(pane_id or '').strip()
    if not pane_text:
        return
    backend._tmux_run(  # type: ignore[attr-defined]
        ['set-option', '-p', '-t', pane_text, 'remain-on-exit', 'on'],
        check=False,
        capture=True,
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
    args.extend(['-c', str(project_root), *_placeholder_spawn_args(backend)])
    backend._tmux_run(args, check=True)  # type: ignore[attr-defined]
    _enable_placeholder_remain_on_exit(
        backend,
        pane_id=session_root_pane(backend, session_name),
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
    result = backend._tmux_run(  # type: ignore[attr-defined]
        ['list-windows', '-t', session_name, '-F', '#{window_id}\t#{window_name}\t#{window_active}'],
        capture=True,
        check=True,
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
    backend._tmux_run(
        [
            'new-window',
            '-d',
            '-t',
            session_name,
            '-n',
            window_name,
            '-c',
            str(project_root),
            *_placeholder_spawn_args(backend),
        ],
        check=True,
    )  # type: ignore[attr-defined]
    record = find_window(backend, session_name=session_name, window_name=window_name)
    if record is None:
        raise RuntimeError(f'failed to resolve tmux window {window_name!r} for session {session_name!r}')
    _enable_placeholder_remain_on_exit(
        backend,
        pane_id=window_root_pane(
            backend,
            target_window=session_window_target(session_name, record.window_id or window_name),
        ),
    )
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


def select_window(backend, *, target: str) -> None:
    backend._tmux_run(['select-window', '-t', target], check=True)  # type: ignore[attr-defined]


def rename_window(backend, *, target: str, new_name: str) -> None:
    backend._tmux_run(['rename-window', '-t', target, new_name], check=True)  # type: ignore[attr-defined]


def kill_window(backend, *, target: str) -> None:
    backend._tmux_run(['kill-window', '-t', target], check=True)  # type: ignore[attr-defined]


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
    result = backend._tmux_run(  # type: ignore[attr-defined]
        ['list-panes', '-t', target_window, '-F', '#{pane_id}'],
        capture=True,
        check=True,
    )
    pane_id = ((result.stdout or '').splitlines() or [''])[0].strip()
    if not pane_id.startswith('%'):
        raise RuntimeError(f'failed to resolve root pane for tmux target {target_window!r}')
    return pane_id


def kill_server(backend, *, session_name: str | None = None) -> bool:
    session_text = str(session_name or '').strip()
    if session_text:
        killer = getattr(backend, 'kill_session', None)
        if callable(killer):
            try:
                return bool(killer(session_text))
            except Exception:
                pass
    try:
        backend._tmux_run(['kill-server'], check=False, capture=True)  # type: ignore[attr-defined]
        return True
    except Exception:
        return False


__all__ = [
    'build_backend',
    'create_session',
    'create_window',
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
    'window_root_pane',
]
