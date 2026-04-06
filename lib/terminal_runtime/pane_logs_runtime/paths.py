from __future__ import annotations

from pathlib import Path

from terminal_runtime.env import sanitize_filename


def pane_log_root() -> Path:
    try:
        from ccbd.runtime import run_dir
    except Exception:
        return Path.home() / '.cache' / 'ccb'
    return run_dir() / 'pane-logs'


def pane_log_dir(backend: str, socket_name: str | None) -> Path:
    root = pane_log_root()
    if backend == 'tmux':
        if socket_name:
            safe = sanitize_filename(socket_name) or 'default'
            return root / f'tmux-{safe}'
        return root / 'tmux'
    safe_backend = sanitize_filename(backend) or 'pane'
    return root / safe_backend


def pane_log_path_for(pane_id: str, backend: str, socket_name: str | None) -> Path:
    pane = str(pane_id or '').strip().replace('%', '')
    safe = sanitize_filename(pane) or 'pane'
    return pane_log_dir(backend, socket_name) / f'pane-{safe}.log'


__all__ = ['pane_log_dir', 'pane_log_path_for', 'pane_log_root']
