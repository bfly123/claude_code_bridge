from __future__ import annotations

from pathlib import Path
from typing import Any

from opencode_runtime.logs import is_cancel_log_line, latest_opencode_log_file, parse_opencode_log_epoch_s
from opencode_runtime.replies import is_aborted_error

from .storage_reader import capture_state, read_messages, read_parts


def detect_cancelled_since(reader, state: dict[str, Any], *, req_id: str) -> tuple[bool, dict[str, Any]]:
    req_id = (req_id or "").strip().lower()
    if not req_id:
        return False, state

    try:
        prev_count = int(state.get("assistant_count") or 0)
    except Exception:
        prev_count = 0
    prev_last = state.get("last_assistant_id")
    prev_completed = state.get("last_assistant_completed")

    new_state = capture_state(reader)
    session_id = new_state.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        return False, new_state

    messages = read_messages(reader, session_id)
    assistants = [
        message for message in messages if message.get("role") == "assistant" and isinstance(message.get("id"), str)
    ]
    by_id: dict[str, dict] = {
        str(message.get("id")): message for message in assistants if isinstance(message.get("id"), str)
    }

    candidates = _candidate_cancel_messages(
        assistants,
        by_id,
        prev_count=prev_count,
        prev_last=prev_last,
        prev_completed=prev_completed,
        new_state=new_state,
    )
    if not candidates:
        return False, new_state

    for message in candidates:
        if not is_aborted_error(message.get("error")):
            continue
        parent_id = message.get("parentID")
        if not isinstance(parent_id, str) or not parent_id:
            continue
        parts = read_parts(reader, parent_id)
        prompt_text = reader._extract_text(parts, allow_reasoning_fallback=True)
        prompt_req_id = reader._extract_req_id_from_text(prompt_text)
        if prompt_req_id and prompt_req_id == req_id:
            return True, new_state

    return False, new_state


def open_cancel_log_cursor() -> dict[str, Any]:
    path = latest_opencode_log_file()
    if not path:
        return {"path": None, "offset": 0}
    try:
        offset = int(path.stat().st_size)
    except Exception:
        offset = 0
    return {"path": str(path), "offset": offset, "mtime": float(path.stat().st_mtime) if path.exists() else 0.0}


def detect_cancel_event_in_logs(
    cursor: dict[str, Any],
    *,
    session_id: str,
    since_epoch_s: float,
) -> tuple[bool, dict[str, Any]]:
    if not isinstance(cursor, dict):
        cursor = {}
    path, offset_i, cursor_mtime_f = _normalize_cursor(cursor)

    latest = latest_opencode_log_file()
    if latest is None:
        return False, {"path": None, "offset": 0, "mtime": 0.0}

    if path is None or not path.exists():
        path = latest
        offset_i = 0
        cursor_mtime_f = 0.0
    elif latest != path:
        try:
            latest_mtime = float(latest.stat().st_mtime)
        except Exception:
            latest_mtime = 0.0
        if latest_mtime > cursor_mtime_f + 0.5:
            path = latest
            offset_i = 0
            cursor_mtime_f = 0.0

    try:
        size = int(path.stat().st_size)
    except Exception:
        return False, {"path": str(path), "offset": 0, "mtime": cursor_mtime_f}

    if offset_i < 0 or offset_i > size:
        offset_i = 0

    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            handle.seek(offset_i)
            chunk = handle.read()
    except Exception:
        return False, {"path": str(path), "offset": size, "mtime": cursor_mtime_f}

    try:
        new_cursor_mtime = float(path.stat().st_mtime)
    except Exception:
        new_cursor_mtime = cursor_mtime_f
    new_cursor = {"path": str(path), "offset": size, "mtime": new_cursor_mtime}
    if not chunk:
        return False, new_cursor

    for line in chunk.splitlines():
        if not is_cancel_log_line(line, session_id=session_id):
            continue
        ts = parse_opencode_log_epoch_s(line)
        if ts is None:
            continue
        if ts + 0.1 < float(since_epoch_s):
            continue
        return True, new_cursor

    return False, new_cursor


def _candidate_cancel_messages(
    assistants: list[dict],
    by_id: dict[str, dict],
    *,
    prev_count: int,
    prev_last,
    prev_completed,
    new_state: dict[str, Any],
) -> list[dict]:
    candidates: list[dict] = []
    if prev_count < len(assistants):
        candidates.extend(assistants[prev_count:])

    last_id = new_state.get("last_assistant_id")
    if isinstance(last_id, str) and last_id in by_id and by_id[last_id] not in candidates:
        candidates.append(by_id[last_id])
    if isinstance(prev_last, str) and prev_last in by_id and prev_last != last_id and by_id[prev_last] not in candidates:
        candidates.append(by_id[prev_last])
    if (
        isinstance(prev_last, str)
        and prev_last in by_id
        and prev_last == last_id
        and by_id[prev_last] not in candidates
        and new_state.get("last_assistant_completed") != prev_completed
    ):
        candidates.append(by_id[prev_last])
    return candidates


def _normalize_cursor(cursor: dict[str, Any]) -> tuple[Path | None, int, float]:
    current_path = cursor.get("path")
    offset = cursor.get("offset")
    cursor_mtime = cursor.get("mtime")
    try:
        offset_i = int(offset) if offset is not None else 0
    except Exception:
        offset_i = 0
    try:
        cursor_mtime_f = float(cursor_mtime) if cursor_mtime is not None else 0.0
    except Exception:
        cursor_mtime_f = 0.0
    path = Path(str(current_path)) if isinstance(current_path, str) and current_path else None
    return path, offset_i, cursor_mtime_f


__all__ = ["detect_cancel_event_in_logs", "detect_cancelled_since", "open_cancel_log_cursor"]
