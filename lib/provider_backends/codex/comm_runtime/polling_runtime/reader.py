from __future__ import annotations

import os
import time
from typing import Any

from ..log_entries import extract_entry, extract_message
from .context import build_cursor, state_payload
from .entries import Extractor, read_matching_from_handle
from .logs import ensure_log, maybe_switch_logs


def read_since(reader, state: dict[str, Any], timeout: float, block: bool) -> tuple[str | None, dict[str, Any]]:
    return _read_matching_since(
        reader,
        state,
        timeout,
        block,
        extractor=extract_message,
        stop_on_missing_timeout=False,
    )


def read_event_since(reader, state: dict[str, Any], timeout: float, block: bool) -> tuple[tuple[str, str] | None, dict[str, Any]]:
    deadline = time.time() + timeout
    current_state = dict(state or {})
    while True:
        remaining = max(0.0, deadline - time.time()) if block else 0.0
        entry, current_state = read_entry_since(reader, current_state, remaining, block=block)
        if entry is None:
            return None, current_state
        role = str(entry.get("role") or "").strip().lower()
        text = str(entry.get("text") or "")
        if role in {"user", "assistant"} and text.strip():
            return (role, text.strip()), current_state
        if not block:
            continue
        if time.time() >= deadline:
            return None, current_state


def read_entry_since(reader, state: dict[str, Any], timeout: float, block: bool) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    return _read_matching_since(
        reader,
        state,
        timeout,
        block,
        extractor=extract_entry,
        stop_on_missing_timeout=True,
    )


def _read_matching_since(
    reader,
    state: dict[str, Any],
    timeout: float,
    block: bool,
    *,
    extractor: Extractor,
    stop_on_missing_timeout: bool,
) -> tuple[Any | None, dict[str, Any]]:
    cursor = build_cursor(state, timeout=timeout)

    while True:
        try:
            log_path = ensure_log(reader, cursor.current_path)
        except FileNotFoundError:
            if not block:
                return None, state_payload(None, 0, last_rescan=cursor.last_rescan)
            time.sleep(reader._poll_interval)
            if stop_on_missing_timeout and time.time() >= cursor.deadline:
                return None, state_payload(None, 0, last_rescan=cursor.last_rescan)
            continue

        try:
            size = log_path.stat().st_size
        except OSError:
            size = None

        if cursor.offset < 0:
            cursor.offset = 0 if cursor.current_path is None else (size if isinstance(size, int) else 0)

        try:
            with log_path.open("rb") as handle:
                try:
                    if isinstance(size, int) and cursor.offset > size:
                        cursor.offset = size
                    handle.seek(cursor.offset, os.SEEK_SET)
                except OSError:
                    cursor.offset = size if isinstance(size, int) else 0
                    if not block:
                        return None, state_payload(log_path, cursor.offset, last_rescan=cursor.last_rescan)
                    time.sleep(reader._poll_interval)
                    continue

                match, cursor.offset = read_matching_from_handle(
                    handle,
                    cursor.offset,
                    extractor=extractor,
                    deadline=cursor.deadline,
                    block=block,
                )
                if match is not None:
                    return match, state_payload(log_path, cursor.offset, last_rescan=cursor.last_rescan)
        except OSError:
            if not block:
                return None, state_payload(log_path, cursor.offset, last_rescan=cursor.last_rescan)
            time.sleep(reader._poll_interval)
            if time.time() >= cursor.deadline:
                return None, state_payload(log_path, cursor.offset, last_rescan=cursor.last_rescan)
            continue

        switched, cursor.current_path, cursor.offset, cursor.last_rescan = maybe_switch_logs(
            reader,
            log_path=log_path,
            current_path=cursor.current_path,
            offset=cursor.offset,
            last_rescan=cursor.last_rescan,
            rescan_interval=cursor.rescan_interval,
        )
        if switched:
            if not block:
                return None, state_payload(cursor.current_path, cursor.offset, last_rescan=cursor.last_rescan)
            time.sleep(reader._poll_interval)
            continue

        if not block:
            return None, state_payload(log_path, cursor.offset, last_rescan=cursor.last_rescan)

        time.sleep(reader._poll_interval)
        if time.time() >= cursor.deadline:
            return None, state_payload(log_path, cursor.offset, last_rescan=cursor.last_rescan)


__all__ = ["read_entry_since", "read_event_since", "read_since"]
