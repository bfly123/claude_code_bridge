from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agents.models import normalize_agent_name

from ..enums import (
    CompletionItemKind,
    CompletionSourceKind,
    CompletionValidationError,
    REPLY_PRIORITY,
    ReplyCandidateKind,
    SCHEMA_VERSION,
)


@dataclass(frozen=True)
class CompletionCursor:
    source_kind: CompletionSourceKind
    opaque_cursor: str | None = None
    session_path: str | None = None
    offset: int | None = None
    line_no: int | None = None
    event_seq: int | None = None
    updated_at: str | None = None

    def __post_init__(self) -> None:
        if self.offset is not None and self.offset < 0:
            raise CompletionValidationError('offset cannot be negative')
        if self.line_no is not None and self.line_no < 0:
            raise CompletionValidationError('line_no cannot be negative')
        if self.event_seq is not None and self.event_seq < 0:
            raise CompletionValidationError('event_seq cannot be negative')

    def to_record(self) -> dict[str, Any]:
        return {
            'schema_version': SCHEMA_VERSION,
            'record_type': 'completion_cursor',
            'source_kind': self.source_kind.value,
            'opaque_cursor': self.opaque_cursor,
            'session_path': self.session_path,
            'offset': self.offset,
            'line_no': self.line_no,
            'event_seq': self.event_seq,
            'updated_at': self.updated_at,
        }


@dataclass(frozen=True)
class CompletionItem:
    kind: CompletionItemKind
    timestamp: str
    cursor: CompletionCursor
    provider: str
    agent_name: str
    req_id: str
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.timestamp:
            raise CompletionValidationError('timestamp cannot be empty')
        provider = (self.provider or '').strip().lower()
        if not provider:
            raise CompletionValidationError('provider cannot be empty')
        object.__setattr__(self, 'provider', provider)
        object.__setattr__(self, 'agent_name', normalize_agent_name(self.agent_name))
        if not (self.req_id or '').strip():
            raise CompletionValidationError('req_id cannot be empty')
        object.__setattr__(self, 'payload', dict(self.payload))

    def to_record(self) -> dict[str, Any]:
        return {
            'schema_version': SCHEMA_VERSION,
            'record_type': 'completion_item',
            'kind': self.kind.value,
            'timestamp': self.timestamp,
            'cursor': self.cursor.to_record(),
            'provider': self.provider,
            'agent_name': self.agent_name,
            'req_id': self.req_id,
            'payload': dict(self.payload),
        }


@dataclass(frozen=True)
class ReplyCandidate:
    kind: ReplyCandidateKind
    text: str
    timestamp: str
    provider_turn_ref: str | None
    priority: int | None
    cursor: CompletionCursor | None

    def __post_init__(self) -> None:
        text = (self.text or '').strip()
        if not text:
            raise CompletionValidationError('reply candidate text cannot be empty')
        if not self.timestamp:
            raise CompletionValidationError('reply candidate timestamp cannot be empty')
        object.__setattr__(self, 'text', text)
        object.__setattr__(self, 'priority', self.priority if self.priority is not None else REPLY_PRIORITY[self.kind])

    def to_record(self) -> dict[str, Any]:
        return {
            'schema_version': SCHEMA_VERSION,
            'record_type': 'reply_candidate',
            'kind': self.kind.value,
            'text': self.text,
            'timestamp': self.timestamp,
            'provider_turn_ref': self.provider_turn_ref,
            'priority': self.priority,
            'cursor': self.cursor.to_record() if self.cursor else None,
        }


__all__ = ['CompletionCursor', 'CompletionItem', 'ReplyCandidate']
