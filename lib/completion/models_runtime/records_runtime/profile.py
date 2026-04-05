from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agents.models import RuntimeMode, normalize_agent_name

from ..enums import CompletionFamily, CompletionSourceKind, CompletionValidationError, SCHEMA_VERSION, SelectorFamily


@dataclass(frozen=True)
class CompletionProfile:
    provider: str
    runtime_mode: RuntimeMode
    completion_family: CompletionFamily
    completion_source_kind: CompletionSourceKind
    supports_exact_completion: bool
    supports_observed_completion: bool
    supports_anchor_binding: bool
    supports_reply_stability: bool
    supports_terminal_reason: bool
    selector_family: SelectorFamily

    def __post_init__(self) -> None:
        provider = (self.provider or '').strip().lower()
        if not provider:
            raise CompletionValidationError('provider cannot be empty')
        object.__setattr__(self, 'provider', provider)

    def to_record(self) -> dict[str, Any]:
        return {
            'schema_version': SCHEMA_VERSION,
            'record_type': 'completion_profile',
            'provider': self.provider,
            'runtime_mode': self.runtime_mode.value,
            'completion_family': self.completion_family.value,
            'completion_source_kind': self.completion_source_kind.value,
            'supports_exact_completion': self.supports_exact_completion,
            'supports_observed_completion': self.supports_observed_completion,
            'supports_anchor_binding': self.supports_anchor_binding,
            'supports_reply_stability': self.supports_reply_stability,
            'supports_terminal_reason': self.supports_terminal_reason,
            'selector_family': self.selector_family.value,
        }


@dataclass(frozen=True)
class CompletionRequestContext:
    req_id: str
    agent_name: str
    provider: str
    timeout_s: float
    anchor_text: str | None = None
    poll_interval_s: float = 0.5

    def __post_init__(self) -> None:
        if not (self.req_id or '').strip():
            raise CompletionValidationError('req_id cannot be empty')
        object.__setattr__(self, 'agent_name', normalize_agent_name(self.agent_name))
        provider = (self.provider or '').strip().lower()
        if not provider:
            raise CompletionValidationError('provider cannot be empty')
        object.__setattr__(self, 'provider', provider)
        if self.timeout_s <= 0:
            raise CompletionValidationError('timeout_s must be positive')
        if self.poll_interval_s <= 0:
            raise CompletionValidationError('poll_interval_s must be positive')

    def to_record(self) -> dict[str, Any]:
        return {
            'schema_version': SCHEMA_VERSION,
            'record_type': 'completion_request_context',
            'req_id': self.req_id,
            'agent_name': self.agent_name,
            'provider': self.provider,
            'timeout_s': self.timeout_s,
            'anchor_text': self.anchor_text,
            'poll_interval_s': self.poll_interval_s,
        }


__all__ = ['CompletionProfile', 'CompletionRequestContext']
