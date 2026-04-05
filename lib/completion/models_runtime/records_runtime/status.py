from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from agents.models import normalize_agent_name

from ..enums import (
    CompletionConfidence,
    CompletionFamily,
    CompletionStatus,
    CompletionValidationError,
    SCHEMA_VERSION,
)
from .protocol import CompletionCursor


@dataclass
class CompletionState:
    anchor_seen: bool = False
    reply_started: bool = False
    reply_stable: bool = False
    tool_active: bool = False
    subagent_activity_seen: bool = False
    last_reply_hash: str | None = None
    last_reply_at: str | None = None
    stable_since: str | None = None
    provider_turn_ref: str | None = None
    latest_cursor: CompletionCursor | None = None
    terminal: bool = False

    def to_record(self) -> dict[str, Any]:
        return {
            'schema_version': SCHEMA_VERSION,
            'record_type': 'completion_state',
            'anchor_seen': self.anchor_seen,
            'reply_started': self.reply_started,
            'reply_stable': self.reply_stable,
            'tool_active': self.tool_active,
            'subagent_activity_seen': self.subagent_activity_seen,
            'last_reply_hash': self.last_reply_hash,
            'last_reply_at': self.last_reply_at,
            'stable_since': self.stable_since,
            'provider_turn_ref': self.provider_turn_ref,
            'latest_cursor': self.latest_cursor.to_record() if self.latest_cursor else None,
            'terminal': self.terminal,
        }


@dataclass(frozen=True)
class CompletionDecision:
    terminal: bool
    status: CompletionStatus
    reason: str | None
    confidence: CompletionConfidence | None
    reply: str
    anchor_seen: bool
    reply_started: bool
    reply_stable: bool
    provider_turn_ref: str | None
    source_cursor: CompletionCursor | None
    finished_at: str | None
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.terminal:
            if self.reason is None:
                raise CompletionValidationError('terminal decisions require reason')
            if self.confidence is None:
                raise CompletionValidationError('terminal decisions require confidence')
            if self.finished_at is None:
                raise CompletionValidationError('terminal decisions require finished_at')
        else:
            if self.status is not CompletionStatus.INCOMPLETE:
                raise CompletionValidationError('non-terminal decisions must use status=incomplete')
            if self.reason is not None or self.confidence is not None or self.finished_at is not None:
                raise CompletionValidationError('non-terminal decisions cannot set reason/confidence/finished_at')
        object.__setattr__(self, 'reply', self.reply or '')
        object.__setattr__(self, 'diagnostics', dict(self.diagnostics))

    @classmethod
    def pending(cls, *, cursor: CompletionCursor | None = None) -> CompletionDecision:
        return cls(
            terminal=False,
            status=CompletionStatus.INCOMPLETE,
            reason=None,
            confidence=None,
            reply='',
            anchor_seen=False,
            reply_started=False,
            reply_stable=False,
            provider_turn_ref=None,
            source_cursor=cursor,
            finished_at=None,
            diagnostics={},
        )

    def with_reply(self, reply: str) -> CompletionDecision:
        return replace(self, reply=reply or self.reply)

    def to_record(self) -> dict[str, Any]:
        return {
            'schema_version': SCHEMA_VERSION,
            'record_type': 'completion_decision',
            'terminal': self.terminal,
            'status': self.status.value,
            'reason': self.reason,
            'confidence': self.confidence.value if self.confidence else None,
            'reply': self.reply,
            'anchor_seen': self.anchor_seen,
            'reply_started': self.reply_started,
            'reply_stable': self.reply_stable,
            'provider_turn_ref': self.provider_turn_ref,
            'source_cursor': self.source_cursor.to_record() if self.source_cursor else None,
            'finished_at': self.finished_at,
            'diagnostics': dict(self.diagnostics),
        }


@dataclass(frozen=True)
class CompletionSnapshot:
    job_id: str
    agent_name: str
    profile_family: CompletionFamily
    state: CompletionState
    latest_decision: CompletionDecision
    latest_reply_preview: str
    updated_at: str

    def __post_init__(self) -> None:
        if not (self.job_id or '').strip():
            raise CompletionValidationError('job_id cannot be empty')
        object.__setattr__(self, 'agent_name', normalize_agent_name(self.agent_name))
        if not self.updated_at:
            raise CompletionValidationError('updated_at cannot be empty')
        object.__setattr__(self, 'latest_reply_preview', self.latest_reply_preview or '')

    def to_record(self) -> dict[str, Any]:
        return {
            'schema_version': SCHEMA_VERSION,
            'record_type': 'completion_snapshot',
            'job_id': self.job_id,
            'agent_name': self.agent_name,
            'profile_family': self.profile_family.value,
            'state': self.state.to_record(),
            'latest_decision': self.latest_decision.to_record(),
            'latest_reply_preview': self.latest_reply_preview,
            'updated_at': self.updated_at,
        }


__all__ = ['CompletionDecision', 'CompletionSnapshot', 'CompletionState']
