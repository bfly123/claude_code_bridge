from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WaitSummary:
    wait_status: str
    project_id: str
    mode: str
    target: str
    resolved_kind: str
    expected_count: int
    received_count: int
    terminal_count: int
    notice_count: int
    waited_s: float
    replies: tuple[dict, ...]


__all__ = ['WaitSummary']
