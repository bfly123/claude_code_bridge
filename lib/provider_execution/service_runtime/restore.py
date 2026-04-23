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
    preflight = restore_preflight_result(service, job, runtime_context=runtime_context)
    if preflight is not None:
        return preflight

    adapter, adapter_result = adapter_or_result(service, job, runtime_context=runtime_context)
    if adapter_result is not None:
        return adapter_result

    persisted, persisted_result = persisted_state_or_result(service, job, runtime_context=runtime_context)
    if persisted_result is not None:
        return persisted_result

    pending_items, _pending_decision = recover_pending_items(service, job.job_id, persisted)
    pending_result = terminal_pending_result(job, persisted, pending_items)
    if pending_result is not None:
        return pending_result

    restored_context = runtime_context
    if persisted.runtime_context is not None:
        if restored_context is None:
            restored_context = persisted.runtime_context
        else:
            restored_context = ProviderRuntimeContext(
                agent_name=str(restored_context.agent_name or persisted.runtime_context.agent_name),
                workspace_path=restored_context.workspace_path or persisted.runtime_context.workspace_path,
                backend_type=restored_context.backend_type or persisted.runtime_context.backend_type,
                runtime_ref=restored_context.runtime_ref or persisted.runtime_context.runtime_ref,
                session_ref=restored_context.session_ref or persisted.runtime_context.session_ref,
                runtime_root=restored_context.runtime_root or persisted.runtime_context.runtime_root,
                runtime_pid=(
                    restored_context.runtime_pid
                    if restored_context.runtime_pid is not None
                    else persisted.runtime_context.runtime_pid
                ),
                runtime_health=restored_context.runtime_health or persisted.runtime_context.runtime_health,
                runtime_binding_source=(
                    restored_context.runtime_binding_source or persisted.runtime_context.runtime_binding_source
                ),
                terminal_backend=restored_context.terminal_backend or persisted.runtime_context.terminal_backend,
                session_file=restored_context.session_file or persisted.runtime_context.session_file,
                session_id=restored_context.session_id or persisted.runtime_context.session_id,
                tmux_socket_name=restored_context.tmux_socket_name or persisted.runtime_context.tmux_socket_name,
                tmux_socket_path=restored_context.tmux_socket_path or persisted.runtime_context.tmux_socket_path,
                job_id=restored_context.job_id or persisted.runtime_context.job_id,
                job_owner_pid=(
                    restored_context.job_owner_pid
                    if restored_context.job_owner_pid is not None
                    else persisted.runtime_context.job_owner_pid
                ),
            )
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
    return restored_result(job, pending_items=pending_items, runtime_context=restored_context)


__all__ = ["restore_submission"]
