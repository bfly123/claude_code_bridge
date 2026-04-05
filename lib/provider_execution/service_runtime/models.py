from __future__ import annotations

from dataclasses import dataclass

from completion.models import CompletionDecision


@dataclass(frozen=True)
class ExecutionUpdate:
    job_id: str
    items: tuple
    decision: CompletionDecision | None


@dataclass(frozen=True)
class ExecutionRestoreResult:
    job_id: str
    agent_name: str
    provider: str
    status: str
    reason: str
    resume_capable: bool
    pending_items_count: int = 0
    decision: CompletionDecision | None = None

    @property
    def restored(self) -> bool:
        return self.status in {"restored", "terminal_pending", "replay_pending"}


__all__ = ["ExecutionRestoreResult", "ExecutionUpdate"]
