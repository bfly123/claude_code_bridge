from __future__ import annotations

from completion.models import CompletionConfidence, CompletionDecision, CompletionStatus

from .records import get_job

_TERMINAL_JOB_STATUSES = frozenset({'completed', 'cancelled', 'failed', 'incomplete'})
_SHUTDOWN_REPLY = 'Project stopped before this request completed.'


def terminate_nonterminal_jobs(
    dispatcher,
    *,
    shutdown_reason: str,
    forced: bool,
) -> tuple:
    terminated = []
    for job_id in _latest_nonterminal_job_ids(dispatcher):
        current = get_job(dispatcher, job_id)
        if current is None or current.status.value in _TERMINAL_JOB_STATUSES:
            continue
        try:
            terminated.append(
                _terminate_job_for_shutdown(
                    dispatcher,
                    current,
                    shutdown_reason=shutdown_reason,
                    forced=forced,
                )
            )
        except Exception:
            continue
    return tuple(terminated)


def _latest_nonterminal_job_ids(dispatcher) -> tuple[str, ...]:
    latest_by_job: dict[str, object] = {}
    ordered_job_ids: list[str] = []
    for agent_name in dispatcher._config.agents:
        for record in dispatcher._job_store.list_agent(agent_name):
            if record.job_id not in latest_by_job:
                ordered_job_ids.append(record.job_id)
            latest_by_job[record.job_id] = record
    return tuple(
        job_id
        for job_id in ordered_job_ids
        if getattr(latest_by_job.get(job_id), 'status', None) is not None
        and latest_by_job[job_id].status.value not in _TERMINAL_JOB_STATUSES
    )


def _terminate_job_for_shutdown(
    dispatcher,
    current,
    *,
    shutdown_reason: str,
    forced: bool,
):
    finished_at = dispatcher._clock()
    dispatcher._state.remove_queued_for(current.target_kind, current.target_name, current.job_id)
    dispatcher._state.clear_active_for(current.target_kind, current.target_name, job_id=current.job_id)
    if dispatcher._execution_service is not None:
        dispatcher._execution_service.cancel(current.job_id)
    snapshot = dispatcher._snapshot_writer.load(current.job_id)
    decision = CompletionDecision(
        terminal=True,
        status=CompletionStatus.INCOMPLETE,
        reason='project_shutdown',
        confidence=CompletionConfidence.DEGRADED,
        reply=_SHUTDOWN_REPLY,
        anchor_seen=snapshot.state.anchor_seen if snapshot is not None else False,
        reply_started=snapshot.state.reply_started if snapshot is not None else False,
        reply_stable=snapshot.state.reply_stable if snapshot is not None else False,
        provider_turn_ref=snapshot.state.provider_turn_ref if snapshot is not None else None,
        source_cursor=snapshot.state.latest_cursor if snapshot is not None else None,
        finished_at=finished_at,
        diagnostics={
            'shutdown': True,
            'shutdown_reason': shutdown_reason,
            'forced': bool(forced),
        },
    )
    return dispatcher.complete(current.job_id, decision)


__all__ = ['terminate_nonterminal_jobs']
