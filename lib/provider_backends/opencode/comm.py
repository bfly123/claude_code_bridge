"""
OpenCode communication module

Reads replies from OpenCode storage (~/.local/share/opencode/storage) and sends messages by
injecting text into the OpenCode TUI pane via the configured terminal backend.
"""

from __future__ import annotations

from terminal_runtime.backend_env import apply_backend_env
from opencode_runtime.paths import OPENCODE_LOG_ROOT, OPENCODE_STORAGE_ROOT
from opencode_runtime.watch import ensure_opencode_watchdog_started as _ensure_opencode_watchdog_started

from .runtime.communicator_facade import OpenCodeCommunicator
from .runtime.log_reader_facade import OpenCodeLogReader

apply_backend_env()

_ensure_opencode_watchdog_started()

__all__ = ["OPENCODE_LOG_ROOT", "OPENCODE_STORAGE_ROOT", "OpenCodeCommunicator", "OpenCodeLogReader"]
