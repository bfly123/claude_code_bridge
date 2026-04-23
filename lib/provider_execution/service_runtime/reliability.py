from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

from ccbd.system import parse_utc_timestamp
from completion.models import CompletionDecision
from provider_execution.base import ProviderPollResult, ProviderSubmission
from provider_execution.common import request_anchor_from_runtime_state
from provider_execution.reliability import adapter_reliability_policy


def apply_reliability_progress(
    result: ProviderPollResult,
    *,
    previous_submission: ProviderSubmission,
    now: str,
) -> ProviderPollResult:
    if not has_reliability_progress(result, previous_submission=previous_submission):
        return result
    updated_submission = with_last_progress_at(result.submission, at=now)
    if updated_submission == result.submission:
        return result
    return ProviderPollResult(
        submission=updated_submission,
        items=result.items,
        decision=result.decision,
    )


def has_reliability_progress(
    result: ProviderPollResult,
    *,
    previous_submission: ProviderSubmission,
) -> bool:
    return bool(
        result.items
        or result.decision is not None
        or result.submission != previous_submission
    )


def with_last_progress_at(submission: ProviderSubmission, *, at: str) -> ProviderSubmission:
    runtime_state = dict(submission.runtime_state)
    if str(runtime_state.get('reliability_last_progress_at') or '').strip() == at:
        return submission
    runtime_state['reliability_last_progress_at'] = at
    return replace(submission, runtime_state=runtime_state)


def timeout_poll_result(
    service,
    *,
    job_id: str,
    submission: ProviderSubmission,
    adapter,
    now: str,
) -> ProviderPollResult | None:
    policy = timeout_policy_for(service, job_id=job_id, adapter=adapter)
    if policy is None:
        return None
    timeout_s = policy.effective_no_terminal_timeout_s()
    if timeout_s <= 0:
        return None
    last_progress_at = last_progress_timestamp(submission)
    if not timeout_elapsed(last_progress_at, now=now, timeout_s=timeout_s):
        return None
    return build_timeout_result(
        submission,
        now=now,
        timeout_s=timeout_s,
        last_progress_at=last_progress_at,
        policy=policy,
    )


def timeout_policy_for(service, *, job_id: str, adapter) -> object | None:
    policy = adapter_reliability_policy(adapter)
    if policy is None:
        return None
    runtime_context = service._runtime_contexts.get(job_id)
    backend_type = str(getattr(runtime_context, 'backend_type', '') or '').strip().lower() or None
    if policy.backend_type and backend_type != policy.backend_type:
        return None
    return policy


def last_progress_timestamp(submission: ProviderSubmission) -> str:
    runtime_state = dict(submission.runtime_state)
    for key in ('reliability_last_progress_at',):
        value = str(runtime_state.get(key) or '').strip()
        if value:
            return value
    return str(submission.ready_at or submission.accepted_at or '').strip()


def timeout_elapsed(started_at: str, *, now: str, timeout_s: float) -> bool:
    if not started_at:
        return False
    try:
        elapsed = (parse_utc_timestamp(now) - parse_utc_timestamp(started_at)).total_seconds()
    except Exception:
        return False
    return elapsed >= max(0.0, timeout_s)


def build_timeout_result(
    submission: ProviderSubmission,
    *,
    now: str,
    timeout_s: float,
    last_progress_at: str,
    policy,
) -> ProviderPollResult:
    reply = str(submission.reply or '')
    request_anchor = request_anchor_from_runtime_state(submission.runtime_state, fallback=submission.job_id)
    diagnostics = {
        **dict(submission.diagnostics or {}),
        'completion_primary_authority': policy.primary_authority,
        'completion_last_progress_at': last_progress_at,
        'completion_timeout_s': timeout_s,
        'completion_timeout_deadline_at': deadline_at(last_progress_at, timeout_s=timeout_s),
        'completion_reliability_reason': policy.timeout_reason,
        'completion_fallback_source': 'execution_reliability_monitor',
    }
    runtime_state = {
        **dict(submission.runtime_state),
        'reliability_last_progress_at': last_progress_at,
        'reliability_timeout_s': timeout_s,
        'reliability_timeout_deadline_at': diagnostics['completion_timeout_deadline_at'] or '',
        'reliability_terminalized_at': now,
    }
    updated_submission = replace(
        submission,
        reply=reply,
        status=policy.timeout_status,
        reason=policy.timeout_reason,
        confidence=policy.timeout_confidence,
        diagnostics=diagnostics,
        runtime_state=runtime_state,
    )
    decision = CompletionDecision(
        terminal=True,
        status=policy.timeout_status,
        reason=policy.timeout_reason,
        confidence=policy.timeout_confidence,
        reply=reply,
        anchor_seen=bool(
            submission.runtime_state.get('anchor_seen')
            or submission.runtime_state.get('anchor_emitted')
        ),
        reply_started=bool(reply),
        reply_stable=bool(reply),
        provider_turn_ref=request_anchor or submission.job_id,
        source_cursor=None,
        finished_at=now,
        diagnostics=diagnostics,
    )
    return ProviderPollResult(submission=updated_submission, decision=decision)


def deadline_at(started_at: str, *, timeout_s: float) -> str | None:
    if not started_at:
        return None
    try:
        deadline = parse_utc_timestamp(started_at) + timedelta(seconds=max(0.0, timeout_s))
    except Exception:
        return None
    return deadline.isoformat().replace('+00:00', 'Z')


__all__ = [
    'apply_reliability_progress',
    'build_timeout_result',
    'deadline_at',
    'has_reliability_progress',
    'last_progress_timestamp',
    'timeout_elapsed',
    'timeout_poll_result',
    'timeout_policy_for',
    'with_last_progress_at',
]
