from __future__ import annotations

from pathlib import Path
import os
import re


def build_tmux_backend(socket_path: str):
    try:
        from terminal_runtime import TmuxBackend

        return TmuxBackend(socket_path=socket_path)
    except Exception:
        return None


def script_path(script_name: str) -> str | None:
    installed = Path.home() / '.local' / 'bin' / script_name
    if installed.is_file():
        return str(installed)
    repo_copy = Path(__file__).resolve().parents[4] / 'config' / script_name
    if repo_copy.is_file():
        return str(repo_copy)
    return None


def detect_ccb_version() -> str:
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


__all__ = ['build_tmux_backend', 'detect_ccb_version', 'script_path']
