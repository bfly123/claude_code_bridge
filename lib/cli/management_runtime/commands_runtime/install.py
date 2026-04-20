from __future__ import annotations

from pathlib import Path

from ..claude_home_cleanup import cleanup_claude_files
from ..install import run_installer


def cmd_uninstall(_args, *, script_root: Path) -> int:
    cleanup_claude_files()
    return run_installer("uninstall", script_root=script_root)


def cmd_reinstall(_args, *, script_root: Path) -> int:
    cleanup_claude_files()
    return run_installer("install", script_root=script_root)


__all__ = ['cmd_reinstall', 'cmd_uninstall']
