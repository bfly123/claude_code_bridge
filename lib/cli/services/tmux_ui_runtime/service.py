from __future__ import annotations

from terminal_runtime.tmux_theme import render_tmux_session_theme

from .helpers import build_tmux_backend, detect_ccb_version, script_path
from .tmux import active_session_pane_id, pane_option_value, tmux_run


def apply_project_tmux_ui(
    *,
    tmux_socket_path: str,
    tmux_session_name: str,
    backend=None,
) -> None:
    socket_path = str(tmux_socket_path or '').strip()
    session_name = str(tmux_session_name or '').strip()
    if not socket_path or not session_name:
        return
    resolved_backend = backend or build_tmux_backend(socket_path)
    if resolved_backend is None:
        return

    status_script = script_path('ccb-status.sh')
    border_script = script_path('ccb-border.sh')
    git_script = script_path('ccb-git.sh')
    ccb_version = detect_ccb_version()
    rendered_theme = render_tmux_session_theme(
        ccb_version=ccb_version,
        status_script=status_script,
        git_script=git_script,
    )

    _apply_session_theme(resolved_backend, session_name=session_name, rendered_theme=rendered_theme)
    _apply_pane_theme(
        resolved_backend,
        session_name=session_name,
        border_script=border_script,
        rendered_theme=rendered_theme,
    )
    _apply_active_pane_border(resolved_backend, session_name=session_name)


def _apply_session_theme(backend, *, session_name: str, rendered_theme) -> None:
    for option, value in rendered_theme.session_options.items():
        tmux_run(backend, ['set-option', '-t', session_name, option, value])


def _apply_pane_theme(backend, *, session_name: str, border_script: str | None, rendered_theme) -> None:
    for option, value in rendered_theme.window_options.items():
        tmux_run(backend, ['set-window-option', '-t', session_name, option, value])
    if border_script is not None:
        hook = f'run-shell "{border_script} \\"#{{pane_id}}\\""'
        tmux_run(backend, ['set-hook', '-t', session_name, 'after-select-pane', hook])


def _apply_active_pane_border(backend, *, session_name: str) -> None:
    active_pane_id = active_session_pane_id(backend, session_name)
    if not active_pane_id:
        return
    style = (
        pane_option_value(backend, active_pane_id, '@ccb_active_border_style')
        or pane_option_value(backend, active_pane_id, '@ccb_border_style')
        or 'fg=#7aa2f7,bold'
    )
    tmux_run(
        backend,
        ['set-option', '-p', '-t', active_pane_id, 'pane-active-border-style', style],
    )


__all__ = ['apply_project_tmux_ui']
