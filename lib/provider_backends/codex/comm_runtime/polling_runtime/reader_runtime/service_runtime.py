from __future__ import annotations

import time
from typing import Any

from ..context import build_cursor, state_payload
from ..entries import Extractor, read_matching_from_handle
from ..logs import ensure_log, maybe_switch_logs

_RETRY_READ = object()


def read_matching_since(
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
        log_path = ensured_log_path(
            reader,
            cursor=cursor,
            block=block,
            stop_on_missing_timeout=stop_on_missing_timeout,
        )
        if log_path is _RETRY_READ:
            continue
        if log_path is None:
            return None, state_payload(None, 0, last_rescan=cursor.last_rescan)

        size = file_size(log_path)
        initialize_offset(cursor, size=size)
        match, offset = read_log_match(
            log_path,
            cursor=cursor,
            extractor=extractor,
            block=block,
            size=size,
        )
        if offset is None:
            state = state_payload(log_path, cursor.offset, last_rescan=cursor.last_rescan)
            if not block or time.time() >= cursor.deadline:
                return None, state
            time.sleep(reader._poll_interval)
            continue
        cursor.offset = offset
        if match is not None:
            return match, state_payload(log_path, cursor.offset, last_rescan=cursor.last_rescan)

        switched = maybe_rotate_log(reader, cursor=cursor, log_path=log_path)
        if switched:
            if not block:
                return no_match_state(cursor.current_path, cursor)
            time.sleep(reader._poll_interval)
            continue

        if not block:
            return no_match_state(log_path, cursor)

        time.sleep(reader._poll_interval)
        if time.time() >= cursor.deadline:
            return no_match_state(log_path, cursor)


def no_match_state(log_path, cursor) -> tuple[None, dict[str, Any]]:
    return None, state_payload(log_path, cursor.offset, last_rescan=cursor.last_rescan)


def ensured_log_path(
    reader,
    *,
    cursor,
    block: bool,
    stop_on_missing_timeout: bool,
):
    try:
        return ensure_log(reader, cursor.current_path)
    except FileNotFoundError:
        if not block:
            return None
        time.sleep(reader._poll_interval)
        if stop_on_missing_timeout and time.time() >= cursor.deadline:
            return None
        return _RETRY_READ


def initialize_offset(cursor, *, size: int | None) -> None:
    if cursor.offset >= 0:
        return
    cursor.offset = 0 if cursor.current_path is None else (size if isinstance(size, int) else 0)


def read_log_match(
    log_path,
    *,
    cursor,
    extractor: Extractor,
    block: bool,
    size: int | None,
) -> tuple[Any | None, int | None]:
    try:
        with log_path.open("rb") as handle:
            offset = seek_to_offset(handle, cursor.offset, size=size)
            if offset is None:
                return None, None
            return read_matching_from_handle(
                handle,
                offset,
                extractor=extractor,
                deadline=cursor.deadline,
                block=block,
            )
    except OSError:
        return None, None


def maybe_rotate_log(reader, *, cursor, log_path) -> bool:
    switched, cursor.current_path, cursor.offset, cursor.last_rescan = maybe_switch_logs(
        reader,
        log_path=log_path,
        current_path=cursor.current_path,
        offset=cursor.offset,
        last_rescan=cursor.last_rescan,
        rescan_interval=cursor.rescan_interval,
    )
    return switched


def file_size(log_path) -> int | None:
    try:
        return log_path.stat().st_size
    except OSError:
        return None


def seek_to_offset(handle, offset: int, *, size: int | None) -> int | None:
    try:
        if isinstance(size, int) and offset > size:
            offset = size
        handle.seek(offset)
        return offset
    except OSError:
        if isinstance(size, int):
            return size
        return None


__all__ = ["read_matching_since"]
