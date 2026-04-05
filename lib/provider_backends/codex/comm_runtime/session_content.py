from __future__ import annotations

import json

from .debug import debug_log_reader, env_int
from .log_entries import extract_message, extract_user_message
from .session_selection import iter_lines_reverse, latest_log


def latest_message(reader) -> str | None:
    log_path = latest_log(reader)
    if not log_path or not log_path.exists():
        return None
    tail_bytes = env_int("CODEX_LOG_TAIL_BYTES", 1024 * 1024 * 8)
    tail_lines = env_int("CODEX_LOG_TAIL_LINES", 5000)
    lines = iter_lines_reverse(reader, log_path, max_bytes=tail_bytes, max_lines=tail_lines)
    if not lines:
        return None

    for line in lines:
        if not line.startswith("{"):
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        message = extract_message(entry)
        if message:
            return message
    debug_log_reader(f"No reply found in tail (bytes={tail_bytes}, lines={tail_lines}) for log: {log_path}")
    return None


def latest_conversations(reader, n: int = 1) -> list[tuple[str, str]]:
    log_path = latest_log(reader)
    if not log_path or not log_path.exists():
        return []
    if n <= 0:
        return []

    tail_bytes = env_int("CODEX_LOG_CONV_TAIL_BYTES", 1024 * 1024 * 32)
    tail_lines = env_int("CODEX_LOG_CONV_TAIL_LINES", 20000)
    lines = iter_lines_reverse(reader, log_path, max_bytes=tail_bytes, max_lines=tail_lines)
    if not lines:
        return []

    pairs_rev: list[tuple[str, str]] = []
    pending_reply: str | None = None

    for line in lines:
        if not line.startswith("{"):
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

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
        debug_log_reader(f"No conversations found in tail (bytes={tail_bytes}, lines={tail_lines}) for log: {log_path}")
    return pairs


__all__ = ["latest_conversations", "latest_message"]
