from __future__ import annotations

from dataclasses import dataclass, replace

from ccbd.api_models import JobRecord, JobStatus
from completion.models import CompletionDecision
from message_bureau import AttemptStore, MessageStore

from .failure_policy import is_nonretryable_api_failure, nonretryable_api_failure_kind

_DEFAULT_RETRYABLE_REASONS = frozenset({'api_error', 'transport_error'})
_DEFAULT_RETRYABLE_ERROR_TYPES = frozenset({'api_error', 'transport_error', 'provider_api_error'})
_DEFAULT_RETRYABLE_RUNTIME_REASONS = frozenset({'pane_dead', 'pane_unavailable', 'runtime_unavailable', 'backend_unavailable'})
_TIMEOUT_INSPECTION_REASONS = frozenset({'timeout'})


@dataclass(frozen=True)
class AutomaticRetryPlan:
    message_id: str
    attempt_id: str
    attempt_number: int
    max_attempts: int
    reason: str


@dataclass(frozen=True)
class RetryableFailureContext:
    message_id: str
    attempt_id: str
    attempt_number: int
    max_attempts: int
    reason: str


def automatic_retry_plan(dispatcher, job: JobRecord, decision: CompletionDecision) -> AutomaticRetryPlan | None:
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
    job: JobRecord,
    decision: CompletionDecision,
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
    if not _is_retryable_failure(
        decision,
        retry_policy=retry_policy,
        provider_supports_resume=_provider_supports_resume(dispatcher, job.provider),
    ):
        return None
    max_attempts = max(_safe_int(retry_policy.get('max_attempts'), 1), 1)
    attempt_number = int(attempt.retry_index) + 1
    return RetryableFailureContext(
        message_id=attempt.message_id,
        attempt_id=attempt.attempt_id,
        attempt_number=attempt_number,
        max_attempts=max_attempts,
        reason=str(decision.reason or '').strip().lower() or 'api_error',
    )


def with_retry_failure_reply(
    decision: CompletionDecision,
    job: JobRecord,
    *,
    attempt_number: int,
    max_attempts: int,
    scheduling_error: str | None = None,
) -> CompletionDecision:
    detail = _retry_failure_detail(decision)
    is_fault_drill = str(decision.diagnostics.get('error_type') or '').strip().lower() == 'fault_injection'
    is_runtime_failure = str(decision.reason or '').strip().lower() in _DEFAULT_RETRYABLE_RUNTIME_REASONS
    if scheduling_error:
        if is_fault_drill:
            reply = (
                f"Fault injection drill forced agent '{job.agent_name}' to fail on attempt "
                f'{attempt_number}/{max_attempts} ({detail}), but automatic retry could not be scheduled '
                f"({scheduling_error}). Execute this task locally or resend it to another healthy registered agent."
            )
        elif is_runtime_failure:
            reply = (
                f"Delivery to agent '{job.agent_name}' hit a retryable runtime/pane failure on attempt "
                f'{attempt_number}/{max_attempts} ({detail}), but automatic retry could not be scheduled '
                f"({scheduling_error}). Execute this task locally or resend it to another healthy registered agent."
            )
        else:
            reply = (
                f"Delivery to agent '{job.agent_name}' hit a retryable provider/API error on attempt "
                f'{attempt_number}/{max_attempts} ({detail}), but automatic retry could not be scheduled '
                f"({scheduling_error}). Execute this task locally or resend it to another healthy registered agent."
            )
    else:
        if is_fault_drill:
            reply = (
                f"Fault injection drill forced agent '{job.agent_name}' to fail after {attempt_number} attempts "
                f'({detail}). Execute this task locally or resend it to another healthy registered agent.'
            )
        elif is_runtime_failure:
            reply = (
                f"Delivery to agent '{job.agent_name}' failed after {attempt_number} attempts because its "
                f'runtime/pane could not be recovered ({detail}). Execute this task locally or resend it '
                'to another healthy registered agent.'
            )
        else:
            reply = (
                f"Delivery to agent '{job.agent_name}' failed after {attempt_number} attempts because the "
                f'provider/API connection kept failing ({detail}). Execute this task locally or resend it '
                'to another healthy registered agent.'
            )
    diagnostics = dict(decision.diagnostics or {})
    diagnostics['auto_retry'] = {
        'attempt_number': attempt_number,
        'max_attempts': max_attempts,
        'scheduling_error': scheduling_error,
    }
    return replace(decision, reply=reply, diagnostics=diagnostics)


def with_nonretryable_api_failure_reply(
    decision: CompletionDecision,
    job: JobRecord,
) -> CompletionDecision:
    detail = _retry_failure_detail(decision)
    kind = nonretryable_api_failure_kind(decision)
    if kind == 'authentication':
        category = 'a non-retryable authentication/login error'
        remediation = 'Fix the provider login/session before retrying locally or resending it.'
    elif kind == 'permission':
        category = 'a non-retryable permission/access error'
        remediation = 'Fix the provider account permissions before retrying locally or resending it.'
    else:
        category = 'a non-retryable quota/billing error'
        remediation = 'Fix the provider billing/quota before retrying locally or resending it.'
    diagnostics = dict(decision.diagnostics or {})
    diagnostics['auto_retry'] = {
        'nonretryable_api_failure': True,
        'classification': kind,
    }
    reply = (
        f"Delivery to agent '{job.agent_name}' failed because the provider/API reported {category} "
        f'({detail}). {remediation} You can also execute this task locally or resend it to another healthy '
        'registered agent.'
    )
    return replace(decision, reply=reply, diagnostics=diagnostics)


def should_render_timeout_inspection_reply(decision: CompletionDecision) -> bool:
    if decision.status.value != JobStatus.INCOMPLETE.value:
        return False
    reason = str(decision.reason or '').strip().lower()
    return reason in _TIMEOUT_INSPECTION_REASONS


def with_timeout_inspection_reply(
    decision: CompletionDecision,
    job: JobRecord,
) -> CompletionDecision:
    diagnostics = dict(decision.diagnostics or {})
    diagnostics['timeout_notice'] = {
        'job_id': job.job_id,
        'agent_name': job.agent_name,
        'action': 'inspect_running_attempt',
    }
    reply = (
        f"Delivery to agent '{job.agent_name}' timed out before a confirmed terminal reply. "
        f"The task may still be running in that agent session. Inspect job '{job.job_id}' in the "
        'agent pane or queue/trace views before deciding whether to continue or retry.'
    )
    return replace(decision, reply=reply, diagnostics=diagnostics)


def _safe_int(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _retryable_reasons(retry_policy: dict[str, object]) -> frozenset[str]:
    configured = {
        str(item or '').strip().lower()
        for item in (retry_policy.get('retryable_reasons') or ())
        if str(item or '').strip()
    }
    return frozenset(configured or _DEFAULT_RETRYABLE_REASONS)


def _retryable_runtime_reasons(retry_policy: dict[str, object]) -> frozenset[str]:
    configured = {
        str(item or '').strip().lower()
        for item in (retry_policy.get('retryable_runtime_reasons') or ())
        if str(item or '').strip()
    }
    return frozenset(configured or _DEFAULT_RETRYABLE_RUNTIME_REASONS)


def _policy_bool(value: object, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    lowered = str(value).strip().lower()
    if lowered in {'1', 'true', 'yes', 'on'}:
        return True
    if lowered in {'0', 'false', 'no', 'off'}:
        return False
    return default


def _provider_supports_resume(dispatcher, provider: str) -> bool:
    try:
        manifest = dispatcher._provider_catalog.get(provider)
    except Exception:
        return False
    return bool(manifest.supports_resume)


def _is_retryable_failure(
    decision: CompletionDecision,
    *,
    retry_policy: dict[str, object],
    provider_supports_resume: bool,
) -> bool:
    if decision.status.value != JobStatus.FAILED.value:
        return False
    if is_nonretryable_api_failure(decision):
        return False
    reason = str(decision.reason or '').strip().lower()
    if reason in _retryable_reasons(retry_policy):
        return True
    if provider_supports_resume and _policy_bool(retry_policy.get('retry_runtime_when_resume_supported'), True):
        if reason in _retryable_runtime_reasons(retry_policy):
            return True
    error_type = str(decision.diagnostics.get('error_type') or '').strip().lower()
    return error_type in _DEFAULT_RETRYABLE_ERROR_TYPES


def _retry_failure_detail(decision: CompletionDecision) -> str:
    parts = []
    reason = str(decision.reason or '').strip()
    if reason:
        parts.append(f'reason={reason}')
    error_type = str(decision.diagnostics.get('error_type') or '').strip()
    if error_type:
        parts.append(f'error_type={error_type}')
    error_code = str(decision.diagnostics.get('error_code') or '').strip()
    if error_code:
        parts.append(f'error_code={error_code}')
    error_message = str(
        decision.diagnostics.get('error_message')
        or decision.diagnostics.get('fault_message')
        or decision.diagnostics.get('error')
        or ''
    ).strip()
    if error_message:
        parts.append(f'error_message={error_message}')
    fault_rule_id = str(decision.diagnostics.get('fault_rule_id') or '').strip()
    if fault_rule_id:
        parts.append(f'fault_rule_id={fault_rule_id}')
    return ', '.join(parts) or 'reason=api_error'


__all__ = [
    'AutomaticRetryPlan',
    'RetryableFailureContext',
    'automatic_retry_plan',
    'retryable_failure_context',
    'should_render_timeout_inspection_reply',
    'with_nonretryable_api_failure_reply',
    'with_timeout_inspection_reply',
    'with_retry_failure_reply',
]
