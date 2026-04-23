from __future__ import annotations

from agents.models import AgentState
from ccbd.api_models import TargetKind
from ccbd.models import CcbdRestoreEntry
from completion.models import CompletionConfidence, CompletionDecision, CompletionStatus

from ..context import build_job_runtime_context
from ..records import append_event, get_job
from ..reply_delivery import is_reply_delivery_job
from ..reply_delivery_runtime.decisions import reply_delivery_failed_decision
from ..runtime_state import sync_runtime


def _restore_entry(current, restored, *, runtime_context=None) -> CcbdRestoreEntry:
    runtime_context = getattr(restored, 'runtime_context', None) or runtime_context
    return CcbdRestoreEntry(
        job_id=current.job_id,
        agent_name=current.agent_name,
        provider=current.provider,
        status=restored.status,
        reason=restored.reason,
        resume_capable=restored.resume_capable,
        pending_items_count=restored.pending_items_count,
        runtime_ref=getattr(runtime_context, 'runtime_ref', None),
        session_ref=getattr(runtime_context, 'session_ref', None),
        session_file=getattr(runtime_context, 'session_file', None),
        session_id=getattr(runtime_context, 'session_id', None),
        terminal_backend=getattr(runtime_context, 'terminal_backend', None),
        runtime_root=getattr(runtime_context, 'runtime_root', None),
        runtime_pid=getattr(runtime_context, 'runtime_pid', None),
        runtime_job_id=getattr(runtime_context, 'job_id', None),
        job_owner_pid=getattr(runtime_context, 'job_owner_pid', None),
    )


def _ensure_completion_tracker(dispatcher, current) -> None:
    if dispatcher._completion_tracker is not None and dispatcher._completion_tracker.current(current.job_id) is None:
        dispatcher._completion_tracker.start(current, started_at=current.updated_at)


def _complete_terminal_pending(dispatcher, current, restored):
    _ensure_completion_tracker(dispatcher, current)
    return dispatcher.complete(current.job_id, restored.decision)


def _mark_restored(dispatcher, current, *, target_kind: TargetKind):
    _ensure_completion_tracker(dispatcher, current)
    if target_kind is TargetKind.AGENT:
        sync_runtime(dispatcher, current.agent_name, state=AgentState.BUSY)
    return current


def _failed_restore_decision(dispatcher, current, restored):
    failed_at = dispatcher._clock()
    diagnostics = {
        'restore_status': restored.status,
        'restore_reason': restored.reason,
        'resume_capable': restored.resume_capable,
    }
    append_event(
        dispatcher,
        current,
        'execution_restore_failed',
        diagnostics,
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
        diagnostics=diagnostics,
    )
    return dispatcher.complete(current.job_id, decision)


def _restore_current_job(dispatcher, *, target_kind: TargetKind, job_id: str):
    current = get_job(dispatcher, job_id)
    if current is None or current.status is not dispatcher._running_status:
        return None, None
    runtime = dispatcher._registry.get(current.agent_name) if target_kind is TargetKind.AGENT else None
    runtime_context = build_job_runtime_context(current, runtime)
    if is_reply_delivery_job(current):
        repaired = dispatcher.complete(
            current.job_id,
            reply_delivery_failed_decision(
                current,
                finished_at=dispatcher._clock(),
                reason='reply_delivery_restart_requeued',
                diagnostics={
                    'restore_status': 'abandoned',
                    'restore_reason': 'reply_delivery_does_not_resume',
                },
            ),
        )
        entry = CcbdRestoreEntry(
            job_id=current.job_id,
            agent_name=current.agent_name,
            provider=current.provider,
            status='abandoned',
            reason='reply_delivery_does_not_resume',
            resume_capable=False,
            pending_items_count=0,
            runtime_ref=getattr(runtime_context, 'runtime_ref', None),
            session_ref=getattr(runtime_context, 'session_ref', None),
            session_file=getattr(runtime_context, 'session_file', None),
            session_id=getattr(runtime_context, 'session_id', None),
            terminal_backend=getattr(runtime_context, 'terminal_backend', None),
            runtime_root=getattr(runtime_context, 'runtime_root', None),
            runtime_pid=getattr(runtime_context, 'runtime_pid', None),
            runtime_job_id=getattr(runtime_context, 'job_id', None),
            job_owner_pid=getattr(runtime_context, 'job_owner_pid', None),
        )
        return repaired, entry
    restored = dispatcher._execution_service.restore(current, runtime_context=runtime_context)
    entry = _restore_entry(current, restored, runtime_context=runtime_context)
    if restored.status == 'terminal_pending' and restored.decision is not None:
        return _complete_terminal_pending(dispatcher, current, restored), entry
    if restored.restored:
        return _mark_restored(dispatcher, current, target_kind=target_kind), entry
    return _failed_restore_decision(dispatcher, current, restored), entry


def restore_running_jobs(dispatcher) -> tuple:
    if dispatcher._execution_service is None:
        return ()
    restored_or_completed: list = []
    restore_entries: list[CcbdRestoreEntry] = []
    dispatcher._last_restore_generated_at = dispatcher._clock()
    for target_kind, _target_name, job_id in dispatcher._state.active_items():
        result, entry = _restore_current_job(dispatcher, target_kind=target_kind, job_id=job_id)
        if entry is None:
            continue
        restore_entries.append(entry)
        restored_or_completed.append(result)
    dispatcher._last_restore_entries = tuple(restore_entries)
    return tuple(restored_or_completed)


__all__ = ["restore_running_jobs"]
