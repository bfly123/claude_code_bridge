from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from ..polling_detection import hash_content
from ..session_content import extract_last_gemini
from ..state import state_payload


@dataclass
class GeminiPollingCursor:
    deadline: float
    prev_count: int
    unknown_baseline: bool
    prev_mtime: float
    prev_mtime_ns: int
    prev_size: int
    prev_session: str | None
    prev_last_gemini_id: str | None
    prev_last_gemini_hash: str | None
    rescan_interval: float
    last_rescan: float
    last_forced_read: float


def build_cursor(state: dict[str, object], *, timeout: float) -> GeminiPollingCursor:
    now = time.time()
    prev_count = state.get("msg_count", 0)
    unknown_baseline = isinstance(prev_count, int) and prev_count < 0
    prev_mtime = state.get("mtime", 0.0)
    prev_mtime_ns = state.get("mtime_ns")
    if prev_mtime_ns is None:
        prev_mtime_ns = int(float(prev_mtime) * 1_000_000_000)
    return GeminiPollingCursor(
        deadline=now + timeout,
        prev_count=prev_count if isinstance(prev_count, int) else 0,
        unknown_baseline=unknown_baseline,
        prev_mtime=float(prev_mtime),
        prev_mtime_ns=int(prev_mtime_ns),
        prev_size=int(state.get("size", 0)),
        prev_session=state.get("session_path"),
        prev_last_gemini_id=state.get("last_gemini_id"),
        prev_last_gemini_hash=state.get("last_gemini_hash"),
        rescan_interval=min(2.0, max(0.2, timeout / 2.0)),
        last_rescan=now,
        last_forced_read=now,
    )


def reset_for_session_switch(cursor: GeminiPollingCursor, *, session: Path) -> None:
    if str(session) == str(cursor.prev_session or ""):
        return
    cursor.prev_count = 0
    cursor.prev_mtime = 0.0
    cursor.prev_mtime_ns = 0
    cursor.prev_size = 0
    cursor.prev_last_gemini_id = None
    cursor.prev_last_gemini_hash = None
    cursor.prev_session = str(session)


def update_from_values(
    cursor: GeminiPollingCursor,
    *,
    session: Path | None,
    current_count: int,
    current_mtime: float,
    current_mtime_ns: int,
    current_size: int,
) -> None:
    cursor.prev_session = str(session) if session is not None else None
    cursor.prev_mtime = current_mtime
    cursor.prev_mtime_ns = current_mtime_ns
    cursor.prev_count = current_count
    cursor.prev_size = current_size


def update_last_gemini(cursor: GeminiPollingCursor, data: dict[str, object]) -> None:
    last = extract_last_gemini(data)
    if not last:
        return
    cursor.prev_last_gemini_id, content = last
    if content:
        cursor.prev_last_gemini_hash = hash_content(content)


def current_state_payload(cursor: GeminiPollingCursor, *, session: Path | None) -> dict[str, object]:
    return state_payload(
        session=session,
        msg_count=cursor.prev_count,
        mtime=cursor.prev_mtime,
        mtime_ns=cursor.prev_mtime_ns,
        size=cursor.prev_size,
        last_gemini_id=cursor.prev_last_gemini_id,
        last_gemini_hash=cursor.prev_last_gemini_hash,
    )


__all__ = [
    "GeminiPollingCursor",
    "build_cursor",
    "current_state_payload",
    "reset_for_session_switch",
    "update_from_values",
    "update_last_gemini",
]
