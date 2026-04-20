from __future__ import annotations


def reply_notice(reply) -> bool:
    diagnostics = _reply_diagnostics(reply)
    if bool(diagnostics.get('notice')):
        return True
    return bool(reply_notice_kind(reply))


def reply_notice_kind(reply) -> str | None:
    diagnostics = _reply_diagnostics(reply)
    value = str(diagnostics.get('notice_kind') or '').strip().lower()
    return value or None


def reply_last_progress_at(reply) -> str | None:
    diagnostics = _reply_diagnostics(reply)
    value = str(diagnostics.get('last_progress_at') or '').strip()
    return value or None


def reply_heartbeat_silence_seconds(reply) -> float | None:
    diagnostics = _reply_diagnostics(reply)
    raw = diagnostics.get('heartbeat_silence_seconds')
    if raw is None:
        return None
    try:
        return float(raw)
    except Exception:
        return None


def _reply_diagnostics(reply) -> dict[str, object]:
    payload = getattr(reply, 'diagnostics', None)
    if isinstance(payload, dict):
        return dict(payload)
    if isinstance(reply, dict):
        diagnostics = reply.get('diagnostics')
        if isinstance(diagnostics, dict):
            return dict(diagnostics)
    return {}


__all__ = [
    'reply_heartbeat_silence_seconds',
    'reply_last_progress_at',
    'reply_notice',
    'reply_notice_kind',
]
