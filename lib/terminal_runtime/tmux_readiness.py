from __future__ import annotations

_TMUX_TRANSIENT_SERVER_ERROR_MARKERS = (
    'fork failed',
    'no server running',
    'server exited unexpectedly',
)
_TMUX_MISSING_SESSION_ERROR_MARKERS = (
    "can't find session",
    'session not found',
)


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


__all__ = [
    'TmuxTransientServerUnavailable',
    'is_tmux_missing_session_text',
    'is_tmux_transient_server_error',
    'is_tmux_transient_server_error_text',
    'tmux_failure_detail',
]
