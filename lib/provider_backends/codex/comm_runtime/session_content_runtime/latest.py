from __future__ import annotations

from ..log_entries import extract_message
from .common import json_entries, log_missing_reply, log_tail


def latest_message(reader) -> str | None:
    default_bytes = 1024 * 1024 * 8
    default_lines = 5000
    log_path, lines = log_tail(
        reader,
        byte_env='CODEX_LOG_TAIL_BYTES',
        line_env='CODEX_LOG_TAIL_LINES',
        default_bytes=default_bytes,
        default_lines=default_lines,
    )
    if not log_path or not lines:
        return None
    for entry in json_entries(lines):
        message = extract_message(entry)
        if message:
            return message
    log_missing_reply(log_path, tail_bytes=default_bytes, tail_lines=default_lines)
    return None


__all__ = ['latest_message']
