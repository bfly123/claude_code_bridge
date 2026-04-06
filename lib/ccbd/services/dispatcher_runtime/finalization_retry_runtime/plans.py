from __future__ import annotations

from message_bureau import AttemptStore, MessageStore

from .models import AutomaticRetryPlan, RetryableFailureContext
from .policy import is_retryable_failure, provider_supports_resume, safe_int


def automatic_retry_plan(dispatcher, job, decision) -> AutomaticRetryPlan | None:
    context = retryable_failure_context(dispatcher, job, decision)
    if context is None or context.attempt_number >= context.max_attempts:
        return None
    return AutomaticRetryPlan(
        message_id=context.message_id,
        attempt_id=context.attempt_id,
        attempt_number=context.attempt_number,
        max_attempts=context.max_attempts,
        reason=context.reason,
    )


def retryable_failure_context(
    dispatcher,
    job,
    decision,
) -> RetryableFailureContext | None:
    attempt = AttemptStore(dispatcher._layout).get_latest_by_job_id(job.job_id)
    if attempt is None:
        return None
    message = MessageStore(dispatcher._layout).get_latest(attempt.message_id)
    if message is None:
        return None
    retry_policy = dict(message.retry_policy or {})
    if str(retry_policy.get('mode') or '').strip().lower() != 'auto':
        return None
    if not is_retryable_failure(
        decision,
        retry_policy=retry_policy,
        provider_supports_resume_value=provider_supports_resume(dispatcher, job.provider),
    ):
        return None
    max_attempts = max(safe_int(retry_policy.get('max_attempts'), 1), 1)
    attempt_number = int(attempt.retry_index) + 1
    return RetryableFailureContext(
        message_id=attempt.message_id,
        attempt_id=attempt.attempt_id,
        attempt_number=attempt_number,
        max_attempts=max_attempts,
        reason=str(decision.reason or '').strip().lower() or 'api_error',
    )


__all__ = ['automatic_retry_plan', 'retryable_failure_context']
