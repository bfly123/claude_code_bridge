from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agents.models_runtime.names import SCHEMA_VERSION

from .helpers import validate_restore_state


@dataclass
class AgentRestoreState:
    restore_mode: object
    last_checkpoint: str | None
    conversation_summary: str
    open_tasks: list[str] = field(default_factory=list)
    files_touched: list[str] = field(default_factory=list)
    base_commit: str | None = None
    head_commit: str | None = None
    last_restore_status: object | None = None

    def __post_init__(self) -> None:
        validate_restore_state(self)

    def to_record(self) -> dict[str, Any]:
        return {
            'schema_version': SCHEMA_VERSION,
            'record_type': 'agent_restore_state',
            'restore_mode': self.restore_mode.value,
            'last_checkpoint': self.last_checkpoint,
            'conversation_summary': self.conversation_summary,
            'open_tasks': list(self.open_tasks),
            'files_touched': list(self.files_touched),
            'base_commit': self.base_commit,
            'head_commit': self.head_commit,
            'last_restore_status': self.last_restore_status.value if self.last_restore_status else None,
        }


__all__ = ['AgentRestoreState']
