from __future__ import annotations

from dataclasses import dataclass

from ccbd.api_models import JobStatus, TargetKind

_PENDING_STATES = frozenset({JobStatus.ACCEPTED, JobStatus.QUEUED})
TargetSlot = tuple[TargetKind, str]


@dataclass
class TargetQueue:
    items: list[str]

    def __init__(self) -> None:
        self.items = []

    def clear(self) -> None:
        self.items.clear()

    def push(self, job_id: str) -> None:
        self.items.append(job_id)

    def pop(self) -> str | None:
        if not self.items:
            return None
        return self.items.pop(0)

    def remove(self, job_id: str) -> bool:
        try:
            self.items.remove(job_id)
        except ValueError:
            return False
        return True

    def __len__(self) -> int:
        return len(self.items)


__all__ = ['TargetQueue', 'TargetSlot', '_PENDING_STATES']
