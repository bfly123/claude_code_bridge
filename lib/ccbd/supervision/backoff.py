from __future__ import annotations

from datetime import timedelta
from pathlib import Path


def is_in_backoff_window(runtime, *, now: str, parse_utc_timestamp_fn, backoff_delay_seconds_fn) -> bool:
    if not str(runtime.last_failure_reason or '').strip():
        return False
    if not str(runtime.last_reconcile_at or '').strip():
        return False
    try:
        checked_at = parse_utc_timestamp_fn(now)
        prior_attempt_at = parse_utc_timestamp_fn(runtime.last_reconcile_at)
    except Exception:
        return False
    delay_s = backoff_delay_seconds_fn(runtime.restart_count)
    return checked_at < (prior_attempt_at + timedelta(seconds=delay_s))


def backoff_delay_seconds(restart_count: int) -> int:
    failures = max(1, int(restart_count or 0))
    return min(2 ** (failures - 1), 30)


def same_socket_path(left: str, right: str) -> bool:
    left_text = str(left or '').strip()
    right_text = str(right or '').strip()
    if not left_text or not right_text:
        return False
    try:
        return Path(left_text).expanduser().resolve() == Path(right_text).expanduser().resolve()
    except Exception:
        return left_text == right_text
