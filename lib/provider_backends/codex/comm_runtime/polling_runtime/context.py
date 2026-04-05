from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from ..pathing import normalize_path


@dataclass
class CodexPollingCursor:
    deadline: float
    current_path: Path | None
    offset: int
    rescan_interval: float
    last_rescan: float


def build_cursor(state: dict[str, object], *, timeout: float) -> CodexPollingCursor:
    offset = state.get("offset", -1)
    if not isinstance(offset, int):
        offset = -1
    now = time.time()
    last_rescan = state.get("last_rescan", now)
    try:
        last_rescan = float(last_rescan)
    except (TypeError, ValueError):
        last_rescan = now
    return CodexPollingCursor(
        deadline=now + timeout,
        current_path=normalize_path(state.get("log_path")),
        offset=offset,
        rescan_interval=min(2.0, max(0.2, timeout / 2.0 if timeout > 0 else 0.2)),
        last_rescan=last_rescan,
    )


def state_payload(log_path: Path | None, offset: int, *, last_rescan: float | None = None) -> dict[str, object]:
    payload: dict[str, object] = {"log_path": log_path, "offset": offset}
    if last_rescan is not None:
        payload["last_rescan"] = float(last_rescan)
    return payload


__all__ = ["CodexPollingCursor", "build_cursor", "state_payload"]
