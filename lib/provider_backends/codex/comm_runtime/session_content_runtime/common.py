from __future__ import annotations

import json

from ..debug import debug_log_reader, env_int
from ..session_selection import iter_lines_reverse, latest_log


def log_tail(reader, *, byte_env: str, line_env: str, default_bytes: int, default_lines: int):
    log_path = latest_log(reader)
    if not log_path or not log_path.exists():
        return None, []
    tail_bytes = env_int(byte_env, default_bytes)
    tail_lines = env_int(line_env, default_lines)
    lines = iter_lines_reverse(reader, log_path, max_bytes=tail_bytes, max_lines=tail_lines)
    return log_path, lines


def json_entries(lines: list[str]):
    for line in lines:
        if not line.startswith('{'):
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        yield entry


def log_missing_reply(log_path, *, tail_bytes: int, tail_lines: int) -> None:
    debug_log_reader(f'No reply found in tail (bytes={tail_bytes}, lines={tail_lines}) for log: {log_path}')


def log_missing_conversations(log_path, *, tail_bytes: int, tail_lines: int) -> None:
    debug_log_reader(f'No conversations found in tail (bytes={tail_bytes}, lines={tail_lines}) for log: {log_path}')


__all__ = ['json_entries', 'log_missing_conversations', 'log_missing_reply', 'log_tail']
