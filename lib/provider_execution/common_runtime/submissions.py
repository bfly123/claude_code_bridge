from __future__ import annotations

from ccbd.api_models import JobRecord
from completion.models import CompletionSourceKind

from provider_execution.base import ProviderSubmission


def passive_submission(
    job: JobRecord,
    *,
    provider: str,
    now: str,
    source_kind: CompletionSourceKind,
    reason: str,
) -> ProviderSubmission:
    return ProviderSubmission(
        job_id=job.job_id,
        agent_name=job.agent_name,
        provider=provider,
        accepted_at=now,
        ready_at=now,
        source_kind=source_kind,
        reply='',
        diagnostics={'provider': provider, 'mode': 'passive', 'reason': reason},
        runtime_state={'mode': 'passive', 'reason': reason},
    )


def error_submission(
    job: JobRecord,
    *,
    provider: str,
    now: str,
    source_kind: CompletionSourceKind,
    reason: str,
    error: str,
) -> ProviderSubmission:
    return ProviderSubmission(
        job_id=job.job_id,
        agent_name=job.agent_name,
        provider=provider,
        accepted_at=now,
        ready_at=now,
        source_kind=source_kind,
        reply='',
        diagnostics={'provider': provider, 'mode': 'error', 'reason': reason, 'error': error},
        runtime_state={'mode': 'error', 'reason': reason, 'error': error, 'next_seq': 1},
    )


__all__ = ['error_submission', 'passive_submission']
