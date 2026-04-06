from __future__ import annotations


def build_backend(backend_factory, *, socket_path: str):
    try:
        return backend_factory(socket_path=socket_path)
    except TypeError:
        return backend_factory()


def prepare_server(backend) -> None:
    backend._tmux_run(['start-server'], check=False, capture=True)  # type: ignore[attr-defined]
    backend._tmux_run(['set-option', '-g', 'destroy-unattached', 'off'], check=False, capture=True)  # type: ignore[attr-defined]


def create_session(backend, *, session_name: str, project_root) -> None:
    backend._tmux_run(
        [
            'new-session',
            '-d',
            '-x',
            '160',
            '-y',
            '48',
            '-s',
            session_name,
            '-c',
            str(project_root),
            'sh',
            '-lc',
            'while :; do sleep 3600; done',
        ],
        check=True,
    )  # type: ignore[attr-defined]


def session_alive(backend, session_name: str) -> bool:
    checker = getattr(backend, 'is_alive', None)
    if not callable(checker):
        return False
    try:
        return bool(checker(session_name))
    except Exception:
        return False


def session_root_pane(backend, session_name: str) -> str:
    result = backend._tmux_run(  # type: ignore[attr-defined]
        ['list-panes', '-t', session_name, '-F', '#{pane_id}'],
        capture=True,
        check=True,
    )
    pane_id = ((result.stdout or '').splitlines() or [''])[0].strip()
    if not pane_id.startswith('%'):
        raise RuntimeError(f'failed to resolve root pane for tmux session {session_name!r}')
    return pane_id


def kill_server(backend) -> bool:
    try:
        backend._tmux_run(['kill-server'], check=False, capture=True)  # type: ignore[attr-defined]
        return True
    except Exception:
        return False


__all__ = [
    'build_backend',
    'create_session',
    'kill_server',
    'prepare_server',
    'session_alive',
    'session_root_pane',
]
