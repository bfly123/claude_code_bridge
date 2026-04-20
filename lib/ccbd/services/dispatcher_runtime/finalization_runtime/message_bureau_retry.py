from __future__ import annotations

from completion.models import CompletionDecision

from ..failure_policy import nonretryable_api_failure_kind
from ..finalization_retry import (
    automatic_retry_plan,
    retryable_failure_context,
    should_render_timeout_inspection_reply,
    with_nonretryable_api_failure_reply,
    with_timeout_inspection_reply,
    with_retry_failure_reply,
)
from .message_bureau_retry_events import (
    append_nonretryable_failure_event,
    append_retry_exhausted_event,
    append_retry_failed_event,
    append_retry_scheduled_event,
)


def schedule_automatic_retry(
    dispatcher,
    current,
    terminal,
    decision: CompletionDecision,
    *,
    finished_at: str,
) -> tuple[CompletionDecision, bool]:
    auto_retry = automatic_retry_plan(dispatcher, current, decision)
    if auto_retry is None:
        return decision, False
    try:
        retry_payload = dispatcher.retry(current.job_id)
    except Exception as exc:
        reply_decision = with_retry_failure_reply(
            decision,
            terminal,
            attempt_number=auto_retry.attempt_number,
            max_attempts=auto_retry.max_attempts,
            scheduling_error=str(exc),
        )
        append_retry_failed_event(
            dispatcher,
            terminal,
            auto_retry,
            error=str(exc),
            finished_at=finished_at,
        )
        return reply_decision, False
    append_retry_scheduled_event(
        dispatcher,
        terminal,
        auto_retry,
        retry_payload,
        finished_at=finished_at,
    )
    return decision, True


def reply_decision_without_automatic_retry(
    dispatcher,
    current,
    terminal,
    decision: CompletionDecision,
    *,
    finished_at: str,
) -> CompletionDecision:
    retryable_failure = retryable_failure_context(dispatcher, current, decision)
    if retryable_failure is not None:
        reply_decision = with_retry_failure_reply(
            decision,
            terminal,
            attempt_number=retryable_failure.attempt_number,
            max_attempts=retryable_failure.max_attempts,
        )
        append_retry_exhausted_event(
            dispatcher,
            terminal,
            retryable_failure,
            finished_at=finished_at,
        )
        return reply_decision
    if should_render_timeout_inspection_reply(decision):
        return with_timeout_inspection_reply(decision, terminal)
    nonretryable_kind = nonretryable_api_failure_kind(decision)
    if nonretryable_kind is None:
        return decision
    reply_decision = with_nonretryable_api_failure_reply(decision, terminal)
    append_nonretryable_failure_event(
        dispatcher,
        terminal,
        decision,
        nonretryable_kind=nonretryable_kind,
        finished_at=finished_at,
    )
    return reply_decision


__all__ = [
    'reply_decision_without_automatic_retry',
    'schedule_automatic_retry',
]
