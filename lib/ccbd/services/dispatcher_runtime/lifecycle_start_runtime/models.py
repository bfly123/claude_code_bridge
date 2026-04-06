from __future__ import annotations

from dataclasses import dataclass

from agents.models import AgentRuntime
from ccbd.api_models import TargetKind


@dataclass(frozen=True)
class QueuedTargetSlot:
    target_kind: TargetKind
    target_name: str
    runtime: AgentRuntime | None = None

    @property
    def requires_runtime_sync(self) -> bool:
        return self.target_kind is TargetKind.AGENT


__all__ = ['QueuedTargetSlot']
