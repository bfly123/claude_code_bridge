from __future__ import annotations

from .api import (
    LayoutResult,
    TerminalBackend,
    TmuxBackend,
    create_auto_layout,
    detect_terminal,
    get_backend,
    get_backend_for_session,
    get_pane_id_from_session,
    get_shell_type,
    is_windows,
    is_wsl,
)

__all__ = [
    "LayoutResult",
    "TerminalBackend",
    "TmuxBackend",
    "create_auto_layout",
    "detect_terminal",
    "get_backend",
    "get_backend_for_session",
    "get_pane_id_from_session",
    "get_shell_type",
    "is_windows",
    "is_wsl",
]
