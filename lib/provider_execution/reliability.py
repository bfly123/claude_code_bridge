from __future__ import annotations

from dataclasses import dataclass
import os

from completion.models import CompletionConfidence, CompletionStatus


@dataclass(frozen=True)
class CompletionReliabilityPolicy:
    provider: str
    no_terminal_timeout_s: float
    primary_authority: str
    backend_type: str | None = 'pane-backed'
    timeout_status: CompletionStatus = CompletionStatus.INCOMPLETE
    timeout_reason: str = 'completion_timeout'
    timeout_confidence: CompletionConfidence = CompletionConfidence.DEGRADED

    def __post_init__(self) -> None:
        provider = str(self.provider or '').strip().lower()
        if not provider:
            raise ValueError('provider cannot be empty')
        object.__setattr__(self, 'provider', provider)
        object.__setattr__(self, 'no_terminal_timeout_s', max(0.0, float(self.no_terminal_timeout_s)))
        backend_type = str(self.backend_type or '').strip().lower() or None
        object.__setattr__(self, 'backend_type', backend_type)

    @property
    def timeout_env_name(self) -> str:
        return f'CCB_{self.provider.upper().replace("-", "_")}_NO_TERMINAL_TIMEOUT_S'

    def effective_no_terminal_timeout_s(self) -> float:
        raw = str(os.environ.get(self.timeout_env_name) or '').strip()
        if not raw:
            return self.no_terminal_timeout_s
        try:
            return max(0.0, float(raw))
        except Exception:
            return self.no_terminal_timeout_s


def adapter_reliability_policy(adapter: object) -> CompletionReliabilityPolicy | None:
    policy = getattr(adapter, 'completion_reliability_policy', None)
    if isinstance(policy, CompletionReliabilityPolicy):
        return policy
    return None


__all__ = ['CompletionReliabilityPolicy', 'adapter_reliability_policy']
