from __future__ import annotations

from ..log_entries import extract_message, extract_user_message
from .common import json_entries, log_missing_conversations, log_tail


def latest_conversations(reader, n: int = 1) -> list[tuple[str, str]]:
    if n <= 0:
        return []
    default_bytes = 1024 * 1024 * 32
    default_lines = 20000
    log_path, lines = log_tail(
        reader,
        byte_env='CODEX_LOG_CONV_TAIL_BYTES',
        line_env='CODEX_LOG_CONV_TAIL_LINES',
        default_bytes=default_bytes,
        default_lines=default_lines,
    )
    if not log_path or not lines:
        return []

    pairs_rev: list[tuple[str, str]] = []
    pending_reply: str | None = None
    for entry in json_entries(lines):
        if pending_reply is None:
            ai_msg = extract_message(entry)
            if ai_msg:
                pending_reply = ai_msg
            continue
        user_msg = extract_user_message(entry)
        if user_msg:
            pairs_rev.append((user_msg, pending_reply))
            pending_reply = None
            if len(pairs_rev) >= n:
                break

    pairs = list(reversed(pairs_rev))
    if not pairs:
        log_missing_conversations(log_path, tail_bytes=default_bytes, tail_lines=default_lines)
    return pairs


__all__ = ['latest_conversations']
