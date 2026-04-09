from __future__ import annotations

from completion.models import CompletionConfidence, CompletionDecision, CompletionStatus


def reply_delivery_completed_decision(
    job,
    *,
    finished_at: str,
    provider_turn_ref: str | None = None,
    diagnostics: dict[str, object] | None = None,
) -> CompletionDecision:
    payload = {
        'reply_delivery': True,
        'delivery_status': 'sent',
    }
    payload.update(dict(diagnostics or {}))
    return CompletionDecision(
        terminal=True,
        status=CompletionStatus.COMPLETED,
        reason='reply_delivery_sent',
        confidence=CompletionConfidence.OBSERVED,
        reply='',
        anchor_seen=True,
        reply_started=False,
        reply_stable=True,
        provider_turn_ref=provider_turn_ref or job.job_id,
        source_cursor=None,
        finished_at=finished_at,
        diagnostics=payload,
    )


def reply_delivery_failed_decision(
    job,
    *,
    finished_at: str,
    reason: str,
    diagnostics: dict[str, object] | None = None,
) -> CompletionDecision:
    payload = {
        'reply_delivery': True,
    }
    payload.update(dict(diagnostics or {}))
    return CompletionDecision(
        terminal=True,
        status=CompletionStatus.INCOMPLETE,
        reason=reason,
        confidence=CompletionConfidence.DEGRADED,
        reply='',
        anchor_seen=False,
        reply_started=False,
        reply_stable=False,
        provider_turn_ref=job.job_id,
        source_cursor=None,
        finished_at=finished_at,
        diagnostics=payload,
    )


__all__ = [
    'reply_delivery_completed_decision',
    'reply_delivery_failed_decision',
]
