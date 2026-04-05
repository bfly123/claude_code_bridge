from __future__ import annotations

from agents.models import AgentState
from ccbd.api_models import TargetKind
from ccbd.models import CcbdRestoreEntry, CcbdRestoreReport
from completion.models import CompletionConfidence, CompletionDecision, CompletionStatus

from .context import build_job_runtime_context
from .records import append_event, get_job
from .runtime_state import sync_runtime


def restore_running_jobs(dispatcher) -> tuple:
    if dispatcher._execution_service is None:
        return ()
    restored_or_completed: list = []
    restore_entries: list[CcbdRestoreEntry] = []
    generated_at = dispatcher._clock()
    for target_kind, _target_name, job_id in dispatcher._state.active_items():
        current = get_job(dispatcher, job_id)
        if current is None or current.status is not dispatcher._running_status:
            continue
        runtime = dispatcher._registry.get(current.agent_name) if target_kind is TargetKind.AGENT else None
        runtime_context = build_job_runtime_context(current, runtime)
        restored = dispatcher._execution_service.restore(current, runtime_context=runtime_context)
        restore_entries.append(
            CcbdRestoreEntry(
                job_id=current.job_id,
                agent_name=current.agent_name,
                provider=current.provider,
                status=restored.status,
                reason=restored.reason,
                resume_capable=restored.resume_capable,
                pending_items_count=restored.pending_items_count,
            )
        )
        if restored.status == 'terminal_pending' and restored.decision is not None:
            if dispatcher._completion_tracker is not None and dispatcher._completion_tracker.current(job_id) is None:
                dispatcher._completion_tracker.start(current, started_at=current.updated_at)
            restored_or_completed.append(dispatcher.complete(job_id, restored.decision))
            continue
        if restored.restored:
            if dispatcher._completion_tracker is not None and dispatcher._completion_tracker.current(job_id) is None:
                dispatcher._completion_tracker.start(current, started_at=current.updated_at)
            if target_kind is TargetKind.AGENT:
                sync_runtime(dispatcher, current.agent_name, state=AgentState.BUSY)
            restored_or_completed.append(current)
            continue

        failed_at = dispatcher._clock()
        append_event(
            dispatcher,
            current,
            'execution_restore_failed',
            {
                'restore_status': restored.status,
                'restore_reason': restored.reason,
                'resume_capable': restored.resume_capable,
            },
            timestamp=failed_at,
        )
        decision = CompletionDecision(
            terminal=True,
            status=CompletionStatus.INCOMPLETE,
            reason='ccbd_restart_requires_resubmit',
            confidence=CompletionConfidence.DEGRADED,
            reply='',
            anchor_seen=False,
            reply_started=False,
            reply_stable=False,
            provider_turn_ref=None,
            source_cursor=None,
            finished_at=failed_at,
            diagnostics={
                'restore_status': restored.status,
                'restore_reason': restored.reason,
                'resume_capable': restored.resume_capable,
            },
        )
        restored_or_completed.append(dispatcher.complete(job_id, decision))
    dispatcher._last_restore_entries = tuple(restore_entries)
    dispatcher._last_restore_generated_at = generated_at
    return tuple(restored_or_completed)


def build_last_restore_report(dispatcher, *, project_id: str) -> CcbdRestoreReport:
    entries = dispatcher._last_restore_entries
    return CcbdRestoreReport(
        project_id=project_id,
        generated_at=dispatcher._last_restore_generated_at or dispatcher._clock(),
        running_job_count=len(entries),
        restored_execution_count=sum(1 for entry in entries if entry.status in {'restored', 'replay_pending'}),
        replay_pending_count=sum(1 for entry in entries if entry.status == 'replay_pending'),
        terminal_pending_count=sum(1 for entry in entries if entry.status == 'terminal_pending'),
        abandoned_execution_count=sum(1 for entry in entries if entry.status == 'abandoned'),
        already_active_count=sum(1 for entry in entries if entry.status == 'already_active'),
        entries=entries,
    )
