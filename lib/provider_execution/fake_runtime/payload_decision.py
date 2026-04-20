from __future__ import annotations

from completion.models import CompletionConfidence, CompletionCursor, CompletionDecision, CompletionStatus

from provider_execution.base import ProviderSubmission


def build_terminal_decision(
    submission: ProviderSubmission,
    *,
    payload: dict[str, object],
    cursor: CompletionCursor,
    finished_at: str,
    reply: str,
) -> CompletionDecision:
    status = CompletionStatus(str(payload.get("status") or submission.status.value))
    confidence = CompletionConfidence(str(payload.get("confidence") or submission.confidence.value))
    reason = str(payload.get("reason") or submission.reason)
    diagnostics = terminal_diagnostics(submission, payload=payload)
    return CompletionDecision(
        terminal=True,
        status=status,
        reason=reason,
        confidence=confidence,
        reply=reply,
        anchor_seen=False,
        reply_started=False,
        reply_stable=False,
        provider_turn_ref=str(payload.get("turn_id") or submission.job_id),
        source_cursor=cursor,
        finished_at=finished_at,
        diagnostics=diagnostics,
    )


def terminal_diagnostics(
    submission: ProviderSubmission,
    *,
    payload: dict[str, object],
) -> dict[str, object]:
    diagnostics = dict(submission.diagnostics or {})
    diagnostics["fake_terminal_kind"] = str(payload.get("kind") or "")
    return diagnostics


__all__ = ["build_terminal_decision"]
