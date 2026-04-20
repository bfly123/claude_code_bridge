from __future__ import annotations

from ccbd.api_models import JobRecord

from provider_execution.base import ProviderRuntimeContext

from .models import ExecutionRestoreResult
from .persistence import filter_pending_items, persist_submission


def adapter_or_result(service, job: JobRecord):
    adapter = service._registry.get(job.provider)
    if adapter is not None:
        return adapter, None
    return None, abandon_restore(
        service,
        job,
        reason='adapter_missing',
        resume_capable=False,
    )


def persisted_state_or_result(service, job: JobRecord):
    persisted = load_persisted_state(service, job)
    if persisted is None:
        return None, result(
            job,
            status='missing',
            reason='state_missing',
            resume_capable=False,
        )
    if persisted.provider == job.provider:
        return persisted, None
    return None, abandon_restore(
        service,
        job,
        reason='provider_mismatch',
        resume_capable=persisted.resume_capable,
        pending_items_count=len(persisted.pending_items),
    )


def recover_pending_items(service, job_id: str, persisted) -> tuple[list, object | None]:
    pending_items = filter_pending_items(persisted)
    if pending_items:
        service._pending_replays[job_id] = (
            pending_items,
            persisted.pending_decision,
        )
    return pending_items, persisted.pending_decision


def terminal_pending_result(job: JobRecord, persisted, pending_items: list) -> ExecutionRestoreResult | None:
    if persisted.pending_decision is None or pending_items:
        return None
    return terminal_pending_restore(job, persisted)


def resume_or_result(adapter, service, job: JobRecord, persisted, pending_items: list, restored_context):
    resume = getattr(adapter, 'resume', None)
    if not persisted.resume_capable or not callable(resume):
        return None, abandon_restore(
            service,
            job,
            reason='provider_resume_unsupported',
            resume_capable=persisted.resume_capable,
            pending_items_count=len(pending_items),
        )
    submission = resume_submission(adapter, service, job, persisted, restored_context)
    if submission is not None:
        return submission, None
    return None, abandon_restore(
        service,
        job,
        reason='provider_resume_rejected',
        resume_capable=persisted.resume_capable,
        pending_items_count=len(pending_items),
    )


def persist_restored_submission(service, job_id: str, submission, *, restored_context, persisted, pending_items: list) -> None:
    service._active[job_id] = submission
    service._runtime_contexts[job_id] = restored_context
    persist_submission(
        service,
        job_id,
        pending_decision=persisted.pending_decision,
        pending_items=pending_items,
        applied_event_seqs=persisted.applied_event_seqs,
    )


def restored_result(job: JobRecord, *, pending_items: list) -> ExecutionRestoreResult:
    return result(
        job,
        status='replay_pending' if pending_items else 'restored',
        reason='pending_items_recovered' if pending_items else 'provider_resumed',
        resume_capable=True,
        pending_items_count=len(pending_items),
    )


def restore_preflight_result(service, job: JobRecord) -> ExecutionRestoreResult | None:
    if job.job_id in service._active:
        return result(
            job,
            status='restored',
            reason='already_active',
            resume_capable=True,
        )
    if service._state_store is None:
        return result(
            job,
            status='missing',
            reason='state_store_disabled',
            resume_capable=False,
        )
    return None


def load_persisted_state(service, job: JobRecord):
    return service._state_store.load(job.job_id)


def abandon_restore(
    service,
    job: JobRecord,
    *,
    reason: str,
    resume_capable: bool,
    pending_items_count: int = 0,
) -> ExecutionRestoreResult:
    service._state_store.remove(job.job_id)
    return result(
        job,
        status='abandoned',
        reason=reason,
        resume_capable=resume_capable,
        pending_items_count=pending_items_count,
    )


def terminal_pending_restore(job: JobRecord, persisted) -> ExecutionRestoreResult:
    return result(
        job,
        status='terminal_pending',
        reason='terminal_decision_recovered',
        resume_capable=persisted.resume_capable,
        decision=persisted.pending_decision,
    )


def resume_submission(adapter, service, job: JobRecord, persisted, restored_context):
    return adapter.resume(
        job,
        persisted.submission,
        context=restored_context,
        persisted_state=persisted,
        now=service._clock(),
    )


def result(
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


__all__ = [
    'adapter_or_result',
    'persisted_state_or_result',
    'recover_pending_items',
    'restore_preflight_result',
    'resume_or_result',
    'persist_restored_submission',
    'restored_result',
    'terminal_pending_result',
]
