from __future__ import annotations

from dataclasses import replace

from completion.models import CompletionDecision

from ..completion import build_terminal_state
from ..failure_policy import nonretryable_api_failure_kind
from ..finalization_retry import (
    automatic_retry_plan,
    retryable_failure_context,
    should_render_timeout_inspection_reply,
    with_nonretryable_api_failure_reply,
    with_timeout_inspection_reply,
    with_retry_failure_reply,
)
from ..records import append_event, append_job


def _append_retry_event(dispatcher, terminal, event_kind: str, payload: dict[str, object], *, timestamp: str) -> None:
    append_event(dispatcher, terminal, event_kind, payload, timestamp=timestamp)


def _append_retry_failed_event(dispatcher, terminal, auto_retry, *, error: str, finished_at: str) -> None:
    _append_retry_event(
        dispatcher,
        terminal,
        'job_retry_failed',
        {
            'message_id': auto_retry.message_id,
            'attempt_id': auto_retry.attempt_id,
            'attempt_number': auto_retry.attempt_number,
            'max_attempts': auto_retry.max_attempts,
            'reason': auto_retry.reason,
            'error': error,
        },
        timestamp=finished_at,
    )


def _append_retry_scheduled_event(
    dispatcher,
    terminal,
    auto_retry,
    retry_payload: dict[str, object],
    *,
    finished_at: str,
) -> None:
    _append_retry_event(
        dispatcher,
        terminal,
        'job_retry_scheduled',
        {
            'message_id': retry_payload.get('message_id'),
            'original_attempt_id': retry_payload.get('original_attempt_id'),
            'attempt_id': retry_payload.get('attempt_id'),
            'job_id': retry_payload.get('job_id'),
            'agent_name': retry_payload.get('agent_name'),
            'attempt_number': auto_retry.attempt_number + 1,
            'max_attempts': auto_retry.max_attempts,
            'reason': auto_retry.reason,
        },
        timestamp=str(retry_payload.get('accepted_at') or finished_at),
    )


def _append_retry_exhausted_event(dispatcher, terminal, retryable_failure, *, finished_at: str) -> None:
    _append_retry_event(
        dispatcher,
        terminal,
        'job_retry_exhausted',
        {
            'message_id': retryable_failure.message_id,
            'attempt_id': retryable_failure.attempt_id,
            'attempt_number': retryable_failure.attempt_number,
            'max_attempts': retryable_failure.max_attempts,
            'reason': retryable_failure.reason,
        },
        timestamp=finished_at,
    )


def _append_nonretryable_failure_event(
    dispatcher,
    terminal,
    decision: CompletionDecision,
    *,
    nonretryable_kind: str,
    finished_at: str,
) -> None:
    _append_retry_event(
        dispatcher,
        terminal,
        'job_retry_skipped_nonretryable',
        {
            'reason': str(decision.reason or '').strip().lower() or 'api_error',
            'classification': nonretryable_kind,
            'error_code': str(decision.diagnostics.get('error_code') or '').strip() or None,
        },
        timestamp=finished_at,
    )


def _schedule_automatic_retry(
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
        _append_retry_failed_event(
            dispatcher,
            terminal,
            auto_retry,
            error=str(exc),
            finished_at=finished_at,
        )
        return reply_decision, False
    _append_retry_scheduled_event(
        dispatcher,
        terminal,
        auto_retry,
        retry_payload,
        finished_at=finished_at,
    )
    return decision, True


def _reply_decision_without_automatic_retry(
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
        _append_retry_exhausted_event(
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
    _append_nonretryable_failure_event(
        dispatcher,
        terminal,
        decision,
        nonretryable_kind=nonretryable_kind,
        finished_at=finished_at,
    )
    return reply_decision


def _persist_reply_decision(dispatcher, current, terminal, reply_decision: CompletionDecision, *, prior_snapshot, finished_at: str):
    terminal = replace(terminal, terminal_decision=reply_decision.to_record())
    append_job(dispatcher, terminal)
    dispatcher._snapshot_writer.write_completion(
        job_id=current.job_id,
        agent_name=current.agent_name,
        profile_family=dispatcher._profile_family_for_job(current),
        state=build_terminal_state(reply_decision, prior_snapshot.state if prior_snapshot else None),
        decision=reply_decision,
        updated_at=finished_at,
    )
    return terminal


def record_message_bureau_completion(
    dispatcher,
    current,
    terminal,
    decision: CompletionDecision,
    *,
    finished_at: str,
    prior_snapshot,
) -> tuple[object, CompletionDecision, bool]:
    reply_decision = decision
    if dispatcher._message_bureau is None:
        return terminal, reply_decision, False

    dispatcher._message_bureau.record_attempt_terminal(terminal, decision, finished_at=finished_at)
    reply_decision, retry_scheduled = _schedule_automatic_retry(
        dispatcher,
        current,
        terminal,
        decision,
        finished_at=finished_at,
    )
    if retry_scheduled:
        return terminal, decision, True
    if reply_decision is decision:
        reply_decision = _reply_decision_without_automatic_retry(
            dispatcher,
            current,
            terminal,
            decision,
            finished_at=finished_at,
        )
    if reply_decision is not decision:
        terminal = _persist_reply_decision(
            dispatcher,
            current,
            terminal,
            reply_decision,
            prior_snapshot=prior_snapshot,
            finished_at=finished_at,
        )
    dispatcher._message_bureau.record_reply(terminal, reply_decision, finished_at=finished_at)
    return terminal, reply_decision, False


__all__ = ['record_message_bureau_completion']
