from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedFaultListCommand:
    project: str | None
    kind: str = 'fault-list'


@dataclass(frozen=True)
class ParsedFaultArmCommand:
    project: str | None
    agent_name: str
    task_id: str
    reason: str
    count: int
    error_message: str
    kind: str = 'fault-arm'


@dataclass(frozen=True)
class ParsedFaultClearCommand:
    project: str | None
    target: str
    kind: str = 'fault-clear'


__all__ = [
    'ParsedFaultArmCommand',
    'ParsedFaultClearCommand',
    'ParsedFaultListCommand',
]
