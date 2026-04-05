from __future__ import annotations

from ccbd.api_models import JobRecord

from provider_execution.base import ProviderRuntimeContext

from .models import ExecutionRestoreResult
from .persistence import filter_pending_items, persist_submission


def restore_submission(
    service,
    job: JobRecord,
    *,
    runtime_context: ProviderRuntimeContext | None = None,
) -> ExecutionRestoreResult:
    provider = job.provider
    if job.job_id in service._active:
        return _result(job, status="restored", reason="already_active", resume_capable=True)
    if service._state_store is None:
        return _result(job, status="missing", reason="state_store_disabled", resume_capable=False)

    adapter = service._registry.get(provider)
    if adapter is None:
        service._state_store.remove(job.job_id)
        return _result(job, status="abandoned", reason="adapter_missing", resume_capable=False)

    persisted = service._state_store.load(job.job_id)
    if persisted is None:
        return _result(job, status="missing", reason="state_missing", resume_capable=False)
    if persisted.provider != provider:
        service._state_store.remove(job.job_id)
        return _result(
            job,
            status="abandoned",
            reason="provider_mismatch",
            resume_capable=persisted.resume_capable,
            pending_items_count=len(persisted.pending_items),
        )

    pending_items = filter_pending_items(persisted)
    if pending_items:
        service._pending_replays[job.job_id] = (pending_items, persisted.pending_decision)
    if persisted.pending_decision is not None and not pending_items:
        return _result(
            job,
            status="terminal_pending",
            reason="terminal_decision_recovered",
            resume_capable=persisted.resume_capable,
            decision=persisted.pending_decision,
        )

    resume = getattr(adapter, "resume", None)
    if not persisted.resume_capable or not callable(resume):
        service._state_store.remove(job.job_id)
        return _result(
            job,
            status="abandoned",
            reason="provider_resume_unsupported",
            resume_capable=persisted.resume_capable,
            pending_items_count=len(pending_items),
        )

    restored_context = runtime_context or persisted.runtime_context
    submission = resume(
        job,
        persisted.submission,
        context=restored_context,
        persisted_state=persisted,
        now=service._clock(),
    )
    if submission is None:
        service._state_store.remove(job.job_id)
        return _result(
            job,
            status="abandoned",
            reason="provider_resume_rejected",
            resume_capable=persisted.resume_capable,
            pending_items_count=len(pending_items),
        )

    service._active[job.job_id] = submission
    service._runtime_contexts[job.job_id] = restored_context
    persist_submission(
        service,
        job.job_id,
        pending_decision=persisted.pending_decision,
        pending_items=pending_items,
        applied_event_seqs=persisted.applied_event_seqs,
    )
    return _result(
        job,
        status="replay_pending" if pending_items else "restored",
        reason="pending_items_recovered" if pending_items else "provider_resumed",
        resume_capable=True,
        pending_items_count=len(pending_items),
    )


def _result(
    job: JobRecord,
    *,
    status: str,
    reason: str,
    resume_capable: bool,
    pending_items_count: int = 0,
    decision=None,
) -> ExecutionRestoreResult:
    return ExecutionRestoreResult(
        job_id=job.job_id,
        agent_name=job.agent_name,
        provider=job.provider,
        status=status,
        reason=reason,
        resume_capable=resume_capable,
        pending_items_count=pending_items_count,
        decision=decision,
    )


__all__ = ["restore_submission"]
