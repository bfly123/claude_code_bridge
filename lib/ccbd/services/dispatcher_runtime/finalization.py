from __future__ import annotations

from dataclasses import replace

from agents.models import AgentState
from ccbd.api_models import JobRecord, JobStatus, TargetKind
from completion.models import CompletionDecision

from .completion import build_terminal_state, merge_terminal_decision
from .failure_policy import nonretryable_api_failure_kind
from .finalization_retry import (
    automatic_retry_plan,
    retryable_failure_context,
    should_render_timeout_inspection_reply,
    with_nonretryable_api_failure_reply,
    with_timeout_inspection_reply,
    with_retry_failure_reply,
)
from .records import append_event, append_job, get_job
from .reply_delivery import resolve_reply_delivery_terminal
from .runtime_state import sync_runtime


def _persist_terminal_completion(
    dispatcher,
    current: JobRecord,
    decision: CompletionDecision,
    *,
    finished_at: str,
) -> tuple[JobRecord, CompletionDecision, object | None]:
    prior_snapshot = dispatcher._snapshot_writer.load(current.job_id)
    terminal_decision = merge_terminal_decision(
        current.job_id,
        decision,
        completion_tracker=dispatcher._completion_tracker,
        prior_snapshot=prior_snapshot,
    )
    if dispatcher._completion_tracker is not None:
        dispatcher._completion_tracker.finish(current.job_id)
    dispatcher._snapshot_writer.write_completion(
        job_id=current.job_id,
        agent_name=current.agent_name,
        profile_family=dispatcher._profile_family_for_job(current),
        state=build_terminal_state(terminal_decision, prior_snapshot.state if prior_snapshot else None),
        decision=terminal_decision,
        updated_at=finished_at,
    )
    append_event(dispatcher, current, 'completion_terminal', terminal_decision.to_record(), timestamp=finished_at)
    terminal = replace(
        current,
        status=JobStatus(terminal_decision.status.value),
        terminal_decision=terminal_decision.to_record(),
        updated_at=finished_at,
    )
    append_job(dispatcher, terminal)
    append_event(
        dispatcher,
        terminal,
        dispatcher._terminal_event_by_status[terminal.status],
        {'status': terminal.status.value},
        timestamp=finished_at,
    )
    dispatcher._state.clear_active_for(current.target_kind, current.target_name, job_id=current.job_id)
    if dispatcher._execution_service is not None:
        dispatcher._execution_service.finish(current.job_id)
    if current.target_kind is TargetKind.AGENT:
        sync_runtime(dispatcher, current.agent_name, state=AgentState.IDLE)
    return terminal, terminal_decision, prior_snapshot


def _record_message_bureau_completion(
    dispatcher,
    current: JobRecord,
    terminal: JobRecord,
    decision: CompletionDecision,
    *,
    finished_at: str,
    prior_snapshot,
) -> tuple[JobRecord, CompletionDecision, bool]:
    reply_decision = decision
    if dispatcher._message_bureau is None:
        return terminal, reply_decision, False

    dispatcher._message_bureau.record_attempt_terminal(terminal, decision, finished_at=finished_at)
    auto_retry = automatic_retry_plan(dispatcher, current, decision)
    retryable_failure = retryable_failure_context(dispatcher, current, decision)
    if auto_retry is not None:
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
            append_event(
                dispatcher,
                terminal,
                'job_retry_failed',
                {
                    'message_id': auto_retry.message_id,
                    'attempt_id': auto_retry.attempt_id,
                    'attempt_number': auto_retry.attempt_number,
                    'max_attempts': auto_retry.max_attempts,
                    'reason': auto_retry.reason,
                    'error': str(exc),
                },
                timestamp=finished_at,
            )
        else:
            append_event(
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
            return terminal, decision, True
    elif retryable_failure is not None:
        reply_decision = with_retry_failure_reply(
            decision,
            terminal,
            attempt_number=retryable_failure.attempt_number,
            max_attempts=retryable_failure.max_attempts,
        )
        append_event(
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
    else:
        if should_render_timeout_inspection_reply(decision):
            reply_decision = with_timeout_inspection_reply(decision, terminal)
        else:
            nonretryable_kind = nonretryable_api_failure_kind(decision)
            if nonretryable_kind is not None:
                reply_decision = with_nonretryable_api_failure_reply(decision, terminal)
                append_event(
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
    if reply_decision is not decision:
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
    dispatcher._message_bureau.record_reply(terminal, reply_decision, finished_at=finished_at)
    return terminal, reply_decision, False


def complete_job(dispatcher, job_id: str, decision: CompletionDecision) -> JobRecord:
    if not decision.terminal:
        raise dispatcher._dispatch_error('complete requires a terminal completion decision')
    current = get_job(dispatcher, job_id)
    if current is None:
        raise dispatcher._dispatch_error(f'unknown job: {job_id}')
    if current.status in dispatcher._terminal_event_by_status:
        return current

    finished_at = decision.finished_at or dispatcher._clock()
    terminal, decision, prior_snapshot = _persist_terminal_completion(
        dispatcher,
        current,
        decision,
        finished_at=finished_at,
    )
    terminal, reply_decision, retry_scheduled = _record_message_bureau_completion(
        dispatcher,
        current,
        terminal,
        decision,
        finished_at=finished_at,
        prior_snapshot=prior_snapshot,
    )
    resolve_reply_delivery_terminal(dispatcher, terminal, finished_at=finished_at)
    if retry_scheduled:
        return terminal
    return terminal


__all__ = ['complete_job']
