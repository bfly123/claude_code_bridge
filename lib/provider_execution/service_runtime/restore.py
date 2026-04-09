from __future__ import annotations

from ccbd.api_models import JobRecord

from provider_execution.base import ProviderRuntimeContext

from .restore_helpers import (
    adapter_or_result,
    persist_restored_submission,
    persisted_state_or_result,
    recover_pending_items,
    restored_result,
    restore_preflight_result,
    resume_or_result,
    terminal_pending_result,
)


def restore_submission(
    service,
    job: JobRecord,
    *,
    runtime_context: ProviderRuntimeContext | None = None,
) -> ExecutionRestoreResult:
    preflight = restore_preflight_result(service, job)
    if preflight is not None:
        return preflight

    adapter, adapter_result = adapter_or_result(service, job)
    if adapter_result is not None:
        return adapter_result

    persisted, persisted_result = persisted_state_or_result(service, job)
    if persisted_result is not None:
        return persisted_result

    pending_items, _pending_decision = recover_pending_items(service, job.job_id, persisted)
    pending_result = terminal_pending_result(job, persisted, pending_items)
    if pending_result is not None:
        return pending_result

    restored_context = runtime_context or persisted.runtime_context
    submission, resume_result = resume_or_result(
        adapter,
        service,
        job,
        persisted,
        pending_items,
        restored_context,
    )
    if resume_result is not None:
        return resume_result

    persist_restored_submission(
        service,
        job.job_id,
        submission,
        restored_context=restored_context,
        persisted=persisted,
        pending_items=pending_items,
    )
    return restored_result(job, pending_items=pending_items)


__all__ = ["restore_submission"]
