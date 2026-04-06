from __future__ import annotations

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

    _apply_session_theme(
        resolved_backend,
        session_name=session_name,
        ccb_version=ccb_version,
        status_script=status_script,
        git_script=git_script,
    )
    _apply_pane_theme(resolved_backend, session_name=session_name, border_script=border_script)
    _apply_active_pane_border(resolved_backend, session_name=session_name)


def _apply_session_theme(backend, *, session_name: str, ccb_version: str, status_script: str | None, git_script: str | None) -> None:
    tmux_run(backend, ['set-option', '-t', session_name, '@ccb_active', '1'])
    tmux_run(backend, ['set-option', '-t', session_name, '@ccb_version', ccb_version])
    tmux_run(backend, ['set-option', '-t', session_name, 'status-position', 'bottom'])
    tmux_run(backend, ['set-option', '-t', session_name, 'status-interval', '5'])
    tmux_run(backend, ['set-option', '-t', session_name, 'status-style', 'bg=#1e1e2e fg=#cdd6f4'])
    tmux_run(backend, ['set-option', '-t', session_name, 'status', '2'])
    tmux_run(backend, ['set-option', '-t', session_name, 'status-left-length', '80'])
    tmux_run(backend, ['set-option', '-t', session_name, 'status-right-length', '120'])
    tmux_run(
        backend,
        [
            'set-option',
            '-t',
            session_name,
            'status-format[1]',
            '#[align=centre,bg=#1e1e2e,fg=#6c7086]Copy: MouseDrag  Paste: Shift-Ctrl-v  Focus: Ctrl-b o',
        ],
    )
    tmux_run(
        backend,
        [
            'set-option',
            '-t',
            session_name,
            'status-format[0]',
            '#[align=left bg=#1e1e2e]#{T:status-left}#[align=centre fg=#6c7086]#{b:pane_current_path}#[align=right]#{T:status-right}',
        ],
    )
    accent = '#{?client_prefix,#f38ba8,#{?pane_in_mode,#fab387,#f5c2e7}}'
    label = '#{?client_prefix,KEY,#{?pane_in_mode,COPY,INPUT}}'
    git_info = f'#({git_script} "#{{pane_current_path}}")' if git_script is not None else '-'
    tmux_run(
        backend,
        [
            'set-option',
            '-t',
            session_name,
            'status-left',
            f'#[fg=#1e1e2e,bg={accent},bold] {label} #[fg={accent},bg=#cba6f7]#[fg=#1e1e2e,bg=#cba6f7] {git_info} #[fg=#cba6f7,bg=#1e1e2e]',
        ],
    )
    focus_agent = '#{?#{@ccb_agent},#{@ccb_agent},-}'
    status_indicator = f'#({status_script} modern "#{{pane_current_path}}")' if status_script is not None else '-'
    status_right = (
        f'#[fg=#f38ba8,bg=#1e1e2e]#[fg=#1e1e2e,bg=#f38ba8,bold] {focus_agent} '
        f'#[fg=#cba6f7,bg=#f38ba8]#[fg=#1e1e2e,bg=#cba6f7,bold] CCB:{ccb_version} '
        f'#[fg=#89b4fa,bg=#cba6f7]#[fg=#cdd6f4,bg=#89b4fa] {status_indicator} '
        '#[fg=#fab387,bg=#89b4fa]#[fg=#1e1e2e,bg=#fab387,bold] %m/%d %a %H:%M #[default]'
    )
    tmux_run(backend, ['set-option', '-t', session_name, 'status-right', status_right])
    tmux_run(backend, ['set-option', '-t', session_name, 'window-status-format', ''])
    tmux_run(backend, ['set-option', '-t', session_name, 'window-status-current-format', ''])
    tmux_run(backend, ['set-option', '-t', session_name, 'window-status-separator', ''])


def _apply_pane_theme(backend, *, session_name: str, border_script: str | None) -> None:
    tmux_run(backend, ['set-window-option', '-t', session_name, 'pane-border-status', 'top'])
    tmux_run(backend, ['set-window-option', '-t', session_name, 'pane-border-style', 'fg=#3b4261,bold'])
    tmux_run(backend, ['set-window-option', '-t', session_name, 'pane-active-border-style', 'fg=#7aa2f7,bold'])
    tmux_run(
        backend,
        [
            'set-window-option',
            '-t',
            session_name,
            'pane-border-format',
            '#{?#{@ccb_agent},#{?#{@ccb_label_style},#{@ccb_label_style},#[fg=#1e1e2e]#[bg=#7aa2f7]#[bold]} #{@ccb_agent} #[default],#[fg=#565f89] #{pane_title} #[default]}',
        ],
    )
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
