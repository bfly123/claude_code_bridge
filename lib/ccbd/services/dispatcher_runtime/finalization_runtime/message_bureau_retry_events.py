from __future__ import annotations

from completion.models import CompletionDecision

from ..records import append_event


def append_retry_event(dispatcher, terminal, event_kind: str, payload: dict[str, object], *, timestamp: str) -> None:
    append_event(dispatcher, terminal, event_kind, payload, timestamp=timestamp)


def append_retry_failed_event(dispatcher, terminal, auto_retry, *, error: str, finished_at: str) -> None:
    append_retry_event(
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


def append_retry_scheduled_event(
    dispatcher,
    terminal,
    auto_retry,
    retry_payload: dict[str, object],
    *,
    finished_at: str,
) -> None:
    append_retry_event(
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


def append_retry_exhausted_event(dispatcher, terminal, retryable_failure, *, finished_at: str) -> None:
    append_retry_event(
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


def append_nonretryable_failure_event(
    dispatcher,
    terminal,
    decision: CompletionDecision,
    *,
    nonretryable_kind: str,
    finished_at: str,
) -> None:
    append_retry_event(
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


__all__ = [
    'append_nonretryable_failure_event',
    'append_retry_exhausted_event',
    'append_retry_failed_event',
    'append_retry_scheduled_event',
]
