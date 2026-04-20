from __future__ import annotations

from .layouts_models import TmuxLayoutBackend


def resolve_root_pane(
    backend: TmuxLayoutBackend,
    *,
    cwd: str,
    root_pane_id: str | None,
    tmux_session_name: str | None,
    detached_session_name: str | None,
    inside_tmux: bool,
) -> tuple[str, bool, list[str]]:
    if root_pane_id:
        return root_pane_id, False, []
    try:
        return backend.get_current_pane_id(), False, []
    except Exception:
        root = detached_root_pane(
            backend,
            cwd=cwd,
            session_name=(tmux_session_name or detached_session_name or '').strip(),
        )
        return root, not inside_tmux, [root]


def detached_root_pane(backend: TmuxLayoutBackend, *, cwd: str, session_name: str) -> str:
    if session_name:
        if not backend.is_alive(session_name):
            backend._tmux_run(['new-session', '-d', '-s', session_name, '-c', cwd], check=True)
        cp = backend._tmux_run(
            ['list-panes', '-t', session_name, '-F', '#{pane_id}'],
            capture=True,
            check=True,
        )
        root = first_pane_id(cp.stdout or '')
    else:
        root = backend.create_pane('', cwd)
    if not root or not root.startswith('%'):
        raise RuntimeError('failed to allocate tmux root pane')
    return root


def first_pane_id(stdout: str) -> str:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    return lines[0] if lines else ''


__all__ = [
    'resolve_root_pane',
]
