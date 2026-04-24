from __future__ import annotations

from terminal_runtime.env import env_float as _env_float_impl

_TMUX_TRANSIENT_SERVER_ERROR_MARKERS = (
    'fork failed',
    'no server running',
    'server exited unexpectedly',
)
_TMUX_MISSING_SESSION_ERROR_MARKERS = (
    "can't find session",
    'session not found',
)
_TMUX_OBJECT_READY_TIMEOUT_S = 3.0
_TMUX_OBJECT_READY_POLL_INTERVAL_S = 0.05


class TmuxTransientServerUnavailable(RuntimeError):
    """tmux server/socket exists as authority, but is not ready for control-plane work yet."""


def tmux_failure_detail(cp: object, args: list[str] | tuple[str, ...] | None = None) -> str:
    stderr = str(getattr(cp, 'stderr', '') or '').strip()
    stdout = str(getattr(cp, 'stdout', '') or '').strip()
    if stderr or stdout:
        return stderr or stdout
    if args:
        return f'tmux command failed: {" ".join(str(item) for item in args)}'
    return 'tmux command failed'


def is_tmux_transient_server_error_text(text: str) -> bool:
    normalized = str(text or '').strip().lower()
    if not normalized:
        return False
    return any(marker in normalized for marker in _TMUX_TRANSIENT_SERVER_ERROR_MARKERS)


def is_tmux_transient_server_error(exc: BaseException) -> bool:
    if isinstance(exc, TmuxTransientServerUnavailable):
        return True
    return is_tmux_transient_server_error_text(str(exc))


def is_tmux_missing_session_text(text: str) -> bool:
    normalized = str(text or '').strip().lower()
    if not normalized:
        return False
    return any(marker in normalized for marker in _TMUX_MISSING_SESSION_ERROR_MARKERS)


def tmux_object_ready_timeout_s(timeout_s: float | None = None) -> float:
    if timeout_s is not None:
        return max(0.0, float(timeout_s))
    return _env_float_impl('CCB_TMUX_OBJECT_READY_TIMEOUT_S', _TMUX_OBJECT_READY_TIMEOUT_S)


def tmux_object_ready_poll_interval_s() -> float:
    return max(0.0, _env_float_impl('CCB_TMUX_OBJECT_READY_POLL_INTERVAL_S', _TMUX_OBJECT_READY_POLL_INTERVAL_S))


__all__ = [
    'TmuxTransientServerUnavailable',
    'is_tmux_missing_session_text',
    'is_tmux_transient_server_error',
    'is_tmux_transient_server_error_text',
    'tmux_object_ready_poll_interval_s',
    'tmux_object_ready_timeout_s',
    'tmux_failure_detail',
]
