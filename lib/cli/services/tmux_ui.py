from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess


def set_tmux_ui_active(active: bool) -> None:
    if not ((os.environ.get('TMUX') or os.environ.get('TMUX_PANE') or '').strip()):
        return
    script = Path.home() / '.local' / 'bin' / ('ccb-tmux-on.sh' if active else 'ccb-tmux-off.sh')
    if not script.is_file():
        return
    try:
        subprocess.run(
            [str(script)],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return


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
    resolved_backend = backend or _build_tmux_backend(socket_path)
    if resolved_backend is None:
        return

    status_script = _script_path('ccb-status.sh')
    border_script = _script_path('ccb-border.sh')
    git_script = _script_path('ccb-git.sh')
    ccb_version = _detect_ccb_version()

    _tmux_run(resolved_backend, ['set-option', '-t', session_name, '@ccb_active', '1'])
    _tmux_run(resolved_backend, ['set-option', '-t', session_name, '@ccb_version', ccb_version])

    _tmux_run(resolved_backend, ['set-option', '-t', session_name, 'status-position', 'bottom'])
    _tmux_run(resolved_backend, ['set-option', '-t', session_name, 'status-interval', os.environ.get('CCB_TMUX_STATUS_INTERVAL', '5')])
    _tmux_run(resolved_backend, ['set-option', '-t', session_name, 'status-style', 'bg=#1e1e2e fg=#cdd6f4'])
    _tmux_run(resolved_backend, ['set-option', '-t', session_name, 'status', '2'])
    _tmux_run(resolved_backend, ['set-option', '-t', session_name, 'status-left-length', '80'])
    _tmux_run(resolved_backend, ['set-option', '-t', session_name, 'status-right-length', '120'])
    _tmux_run(
        resolved_backend,
        [
            'set-option',
            '-t',
            session_name,
            'status-format[1]',
            '#[align=centre,bg=#1e1e2e,fg=#6c7086]Copy: MouseDrag  Paste: Shift-Ctrl-v  Focus: Ctrl-b o',
        ],
    )
    _tmux_run(
        resolved_backend,
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
    git_info = '-'
    if git_script is not None:
        git_info = f'#({git_script} "#{{pane_current_path}}")'
    _tmux_run(
        resolved_backend,
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
    _tmux_run(resolved_backend, ['set-option', '-t', session_name, 'status-right', status_right])
    _tmux_run(resolved_backend, ['set-option', '-t', session_name, 'window-status-format', ''])
    _tmux_run(resolved_backend, ['set-option', '-t', session_name, 'window-status-current-format', ''])
    _tmux_run(resolved_backend, ['set-option', '-t', session_name, 'window-status-separator', ''])

    _tmux_run(resolved_backend, ['set-window-option', '-t', session_name, 'pane-border-status', 'top'])
    _tmux_run(resolved_backend, ['set-window-option', '-t', session_name, 'pane-border-style', 'fg=#3b4261,bold'])
    _tmux_run(resolved_backend, ['set-window-option', '-t', session_name, 'pane-active-border-style', 'fg=#7aa2f7,bold'])
    _tmux_run(
        resolved_backend,
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
        _tmux_run(resolved_backend, ['set-hook', '-t', session_name, 'after-select-pane', hook])

    active_pane_id = _active_session_pane_id(resolved_backend, session_name)
    if active_pane_id:
        style = (
            _pane_option_value(resolved_backend, active_pane_id, '@ccb_active_border_style')
            or _pane_option_value(resolved_backend, active_pane_id, '@ccb_border_style')
            or 'fg=#7aa2f7,bold'
        )
        _tmux_run(
            resolved_backend,
            ['set-option', '-p', '-t', active_pane_id, 'pane-active-border-style', style],
        )


def _build_tmux_backend(socket_path: str):
    try:
        from terminal_runtime import TmuxBackend

        return TmuxBackend(socket_path=socket_path)
    except Exception:
        return None


def _tmux_run(backend, args: list[str]) -> None:
    try:
        backend._tmux_run(args, check=False, capture=True)  # type: ignore[attr-defined]
    except Exception:
        return


def _capture_tmux_value(backend, args: list[str]) -> str | None:
    try:
        result = backend._tmux_run(args, check=False, capture=True)  # type: ignore[attr-defined]
    except Exception:
        return None
    if getattr(result, 'returncode', 1) != 0:
        return None
    return ((getattr(result, 'stdout', '') or '').splitlines() or [''])[0].strip() or None


def _active_session_pane_id(backend, session_name: str) -> str | None:
    try:
        result = backend._tmux_run(  # type: ignore[attr-defined]
            ['list-panes', '-t', session_name, '-F', '#{?pane_active,#{pane_id},}'],
            check=False,
            capture=True,
        )
    except Exception:
        return None
    if getattr(result, 'returncode', 1) != 0:
        return None
    for line in (getattr(result, 'stdout', '') or '').splitlines():
        pane_id = str(line or '').strip()
        if pane_id:
            return pane_id
    return None


def _pane_option_value(backend, pane_id: str, option_name: str) -> str | None:
    return _capture_tmux_value(
        backend,
        ['display-message', '-p', '-t', pane_id, f'#{{{option_name}}}'],
    )


def _script_path(script_name: str) -> str | None:
    installed = Path.home() / '.local' / 'bin' / script_name
    if installed.is_file():
        return str(installed)
    repo_copy = Path(__file__).resolve().parents[3] / 'config' / script_name
    if repo_copy.is_file():
        return str(repo_copy)
    return None


def _detect_ccb_version() -> str:
    env_version = str(os.environ.get('CCB_VERSION') or '').strip()
    if env_version:
        return env_version
    ccb_path = Path.home() / '.local' / 'bin' / 'ccb'
    if not ccb_path.is_file():
        return '?'
    try:
        text = ccb_path.read_text(encoding='utf-8', errors='replace')
    except Exception:
        return '?'
    match = re.search(r'VERSION = "([^"]+)"', text)
    if match is None:
        return '?'
    return str(match.group(1)).strip() or '?'


__all__ = ['apply_project_tmux_ui', 'set_tmux_ui_active']
