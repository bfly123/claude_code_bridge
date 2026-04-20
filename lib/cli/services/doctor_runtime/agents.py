from __future__ import annotations

from provider_execution.capabilities import execution_restore_capability

from ..provider_binding import binding_status


def agent_summaries(
    context,
    *,
    config,
    stores: dict[str, object],
    catalog,
    execution_registry,
    errors: list[str],
) -> list[dict]:
    agents: list[dict] = []
    for agent_name, spec in sorted(config.agents.items()):
        runtime = stores['runtime'].load_best_effort(agent_name)
        latest_snapshot = latest_snapshot_for_agent(
            context,
            agent_name=agent_name,
            runtime=runtime,
            snapshot_store=stores['snapshot'],
            errors=errors,
        )
        agents.append(
            agent_summary(
                context,
                agent_name=agent_name,
                spec=spec,
                runtime=runtime,
                latest_snapshot=latest_snapshot,
                catalog=catalog,
                execution_registry=execution_registry,
            )
        )
    return agents


def latest_snapshot_for_agent(
    context,
    *,
    agent_name: str,
    runtime,
    snapshot_store,
    errors: list[str],
):
    if runtime is None:
        return None
    jobs_path = context.paths.job_store_path(agent_name)
    if not jobs_path.exists():
        return None
    from jobs.store import JobStore

    try:
        job_store = JobStore(context.paths)
        jobs = job_store.list_agent(agent_name)
    except Exception as exc:
        errors.append(f'job_store:{agent_name}:{exc}')
        return None
    if not jobs:
        return None
    return snapshot_store.load(jobs[-1].job_id)


def agent_summary(
    context,
    *,
    agent_name: str,
    spec,
    runtime,
    latest_snapshot,
    catalog,
    execution_registry,
) -> dict:
    workspace_path = resolved_workspace_path(context, agent_name=agent_name, runtime=runtime)
    runtime_ref = getattr(runtime, 'runtime_ref', None)
    session_ref = runtime_session_ref(runtime)
    manifest = catalog.resolve_completion_manifest(spec.provider, spec.runtime_mode)
    capability = execution_restore_capability(execution_registry.get(spec.provider), provider=spec.provider)
    return {
        'agent_name': agent_name,
        'provider': spec.provider,
        'runtime_mode': spec.runtime_mode.value,
        'workspace_path': workspace_path,
        'workspace_mode': spec.workspace_mode.value,
        'branch_name': None,
        'completion_family': manifest.completion_family.value,
        'completion_confidence': snapshot_confidence(latest_snapshot),
        'last_completion_reason': snapshot_reason(latest_snapshot),
        'queue_depth': getattr(runtime, 'queue_depth', 0) if runtime is not None else 0,
        'health': getattr(runtime, 'health', 'stopped') if runtime is not None else 'stopped',
        'runtime_ref': runtime_ref,
        'session_ref': session_ref,
        'backend_type': getattr(runtime, 'backend_type', spec.runtime_mode.value) if runtime is not None else spec.runtime_mode.value,
        'binding_status': binding_status(runtime_ref, session_ref, workspace_path),
        'binding_source': getattr(getattr(runtime, 'binding_source', None), 'value', 'provider-session') if runtime is not None else 'provider-session',
        'terminal': getattr(runtime, 'terminal_backend', None) if runtime is not None else None,
        'tmux_socket_name': getattr(runtime, 'tmux_socket_name', None) if runtime is not None else None,
        'tmux_socket_path': getattr(runtime, 'tmux_socket_path', None) if runtime is not None else None,
        'pane_id': getattr(runtime, 'pane_id', None) if runtime is not None else None,
        'active_pane_id': getattr(runtime, 'active_pane_id', None) if runtime is not None else None,
        'pane_title_marker': getattr(runtime, 'pane_title_marker', None) if runtime is not None else None,
        'pane_state': getattr(runtime, 'pane_state', None) if runtime is not None else None,
        'execution_resume_supported': capability['resume_supported'],
        'execution_restore_mode': capability['restore_mode'],
        'execution_restore_reason': capability['restore_reason'],
        'execution_restore_detail': capability['restore_detail'],
    }


def resolved_workspace_path(context, *, agent_name: str, runtime) -> str:
    if runtime is not None and runtime.workspace_path:
        return runtime.workspace_path
    return str(context.paths.workspace_path(agent_name))


def runtime_session_ref(runtime) -> str | None:
    if runtime is None:
        return None
    return runtime.session_id or runtime.session_ref or runtime.session_file


def snapshot_confidence(latest_snapshot):
    if latest_snapshot is None or latest_snapshot.latest_decision.confidence is None:
        return None
    return latest_snapshot.latest_decision.confidence.value


def snapshot_reason(latest_snapshot):
    if latest_snapshot is None:
        return None
    return latest_snapshot.latest_decision.reason


__all__ = ['agent_summaries']
