from __future__ import annotations

import os
import shutil
from typing import Optional

from terminal_runtime.backend_types import TerminalBackend
from terminal_runtime.backend_env import default_mux_backend_impl as _default_mux_backend_impl
from terminal_runtime.detect import current_tty as _current_tty_impl
from terminal_runtime.detect import detect_terminal as _detect_terminal_impl
from terminal_runtime.detect import inside_tmux as _inside_tmux_impl
from terminal_runtime.env import default_shell as _default_shell_impl
from terminal_runtime.env import env_float as _env_float_impl
from terminal_runtime.env import env_int as _env_int_impl
from terminal_runtime.env import is_windows as _is_windows_impl
from terminal_runtime.env import is_wsl as _is_wsl_impl
from terminal_runtime.env import sanitize_filename as _sanitize_filename_impl
from terminal_runtime.env import subprocess_kwargs as _subprocess_kwargs_impl
from terminal_runtime.layouts import LayoutResult
from terminal_runtime.mux_backend import MuxBackend
from terminal_runtime.pane_logs import cleanup_pane_logs as _cleanup_pane_logs_impl
from terminal_runtime.pane_logs import maybe_trim_log as _maybe_trim_log_impl
from terminal_runtime.pane_logs import pane_log_dir as _pane_log_dir_impl
from terminal_runtime.pane_logs import pane_log_path_for as _pane_log_path_for_impl
from terminal_runtime.pane_logs import pane_log_root as _pane_log_root_impl
from terminal_runtime.tmux import default_detached_session_name as _default_detached_session_name_impl
from terminal_runtime.psmux_backend import PsmuxBackend
from terminal_runtime.tmux_backend import TmuxBackend

from .api_selection import (
    create_layout as _create_layout,
    resolve_backend as _resolve_backend,
    resolve_backend_for_session as _resolve_backend_for_session,
    resolve_pane_id_from_session as _resolve_pane_id_from_session,
)

_env_float = _env_float_impl
_env_int = _env_int_impl
_sanitize_filename = _sanitize_filename_impl
_pane_log_root = _pane_log_root_impl
_pane_log_dir = _pane_log_dir_impl
_pane_log_path_for = _pane_log_path_for_impl
_maybe_trim_log = _maybe_trim_log_impl
_cleanup_pane_logs = _cleanup_pane_logs_impl
is_windows = _is_windows_impl
_subprocess_kwargs = _subprocess_kwargs_impl
is_wsl = _is_wsl_impl
_current_tty = _current_tty_impl


def _run(*args, **kwargs):
    kwargs.update(_subprocess_kwargs())
    import subprocess as _sp

    return _sp.run(*args, **kwargs)

def _default_shell() -> tuple[str, str]:
    return _default_shell_impl(is_wsl_fn=is_wsl, is_windows_fn=is_windows)


def get_shell_type() -> str:
    if is_windows() and os.environ.get("CCB_BACKEND_ENV", "").lower() == "wsl":
        return "bash"
    shell, _ = _default_shell()
    if shell in ("pwsh", "powershell"):
        return "powershell"
    return "bash"


_backend_cache: Optional[TerminalBackend] = None


def mux_backend_cls_for_impl(backend_impl: str | None):
    impl = str(backend_impl or '').strip().lower()
    if impl == 'psmux':
        return PsmuxBackend
    return TmuxBackend


def default_mux_backend_cls():
    return mux_backend_cls_for_impl(_default_mux_backend_impl())


def build_mux_backend(*, backend_impl: str | None = None, socket_name: str | None = None, socket_path: str | None = None):
    backend_cls = mux_backend_cls_for_impl(backend_impl) if backend_impl is not None else default_mux_backend_cls()
    try:
        return backend_cls(socket_name=socket_name, socket_path=socket_path)
    except TypeError:
        return backend_cls()


def _inside_tmux() -> bool:
    return _inside_tmux_impl(
        env=os.environ,
        which_fn=shutil.which,
        run_fn=_run,
        current_tty_fn=_current_tty,
    )


def detect_terminal() -> Optional[str]:
    return _detect_terminal_impl(
        env=os.environ,
        which_fn=shutil.which,
        run_fn=_run,
        current_tty_fn=_current_tty,
    )


def get_backend(terminal_type: Optional[str] = None) -> Optional[TerminalBackend]:
    global _backend_cache
    _backend_cache = _resolve_backend(
        cached_backend=_backend_cache,
        terminal_type=terminal_type,
        detect_terminal_fn=detect_terminal,
        tmux_backend_factory=default_mux_backend_cls(),
    )
    return _backend_cache


def get_backend_for_session(session_data: dict) -> Optional[TerminalBackend]:
    return _resolve_backend_for_session(
        session_data=session_data,
        detect_terminal_fn=detect_terminal,
        tmux_backend_factory=default_mux_backend_cls(),
    )


def get_pane_id_from_session(session_data: dict) -> Optional[str]:
    return _resolve_pane_id_from_session(session_data)


def create_auto_layout(
    providers: list[str],
    *,
    cwd: str,
    root_pane_id: str | None = None,
    tmux_session_name: str | None = None,
    percent: int = 50,
    set_markers: bool = True,
    marker_prefix: str = "CCB",
) -> LayoutResult:
    return _create_layout(
        providers=providers,
        cwd=cwd,
        root_pane_id=root_pane_id,
        tmux_session_name=tmux_session_name,
        percent=percent,
        set_markers=set_markers,
        marker_prefix=marker_prefix,
        tmux_backend_factory=default_mux_backend_cls(),
        detached_session_name_fn=_default_detached_session_name_impl,
        env=os.environ,
    )


__all__ = [
    "LayoutResult",
    "MuxBackend",
    "TerminalBackend",
    "PsmuxBackend",
    "TmuxBackend",
    "build_mux_backend",
    "create_auto_layout",
    "default_mux_backend_cls",
    "detect_terminal",
    "get_backend",
    "get_backend_for_session",
    "get_pane_id_from_session",
    "get_shell_type",
    "is_windows",
    "is_wsl",
    "mux_backend_cls_for_impl",
]
