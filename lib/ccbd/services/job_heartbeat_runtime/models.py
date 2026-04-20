from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HeartbeatTickContext:
    snapshot: object | None
    observed_last_progress_at: str
    now: str
    next_state: object
    decision: object


__all__ = ['HeartbeatTickContext']
