from __future__ import annotations

from agents.config_loader import load_project_config
from agents.store import AgentRuntimeStore
from ccbd.lifecycle_report_store import CcbdShutdownReportStore, CcbdStartupReportStore
from ccbd.restore_report_store import CcbdRestoreReportStore
from ccbd.services.project_namespace_state import ProjectNamespaceEventStore, ProjectNamespaceStateStore
from ccbd.services.start_policy import CcbdStartPolicyStore
from cli.context import CliContext
from completion.snapshot_store import CompletionSnapshotStore
from provider_core.catalog import build_default_provider_catalog
from provider_execution.capabilities import execution_restore_capability
from provider_execution.registry import build_default_execution_registry
from provider_execution.state_store import ExecutionStateStore

from .daemon import ping_local_state
from .provider_binding import binding_status
from .tmux_cleanup_history import TmuxCleanupHistoryStore


def doctor_summary(context: CliContext) -> dict:
    config = load_project_config(context.project.project_root).config
    stores = _doctor_stores(context)
    catalog = build_default_provider_catalog()
    execution_registry = build_default_execution_registry()
    local = ping_local_state(context)
    errors: list[str] = []
    agents = _agent_summaries(
        context,
        config=config,
        stores=stores,
        catalog=catalog,
        execution_registry=execution_registry,
        errors=errors,
    )
    return {
        'project': str(context.project.project_root),
        'project_id': context.project.project_id,
        'ccbd': _ccbd_summary(local=local, stores=stores, errors=errors),
        'agents': agents,
    }


def _doctor_stores(context: CliContext) -> dict[str, object]:
    return {
        'runtime': AgentRuntimeStore(context.paths),
        'snapshot': CompletionSnapshotStore(context.paths),
        'execution_state': ExecutionStateStore(context.paths),
        'restore_report': CcbdRestoreReportStore(context.paths),
        'startup_report': CcbdStartupReportStore(context.paths),
        'shutdown_report': CcbdShutdownReportStore(context.paths),
        'namespace_state': ProjectNamespaceStateStore(context.paths),
        'namespace_event': ProjectNamespaceEventStore(context.paths),
        'start_policy': CcbdStartPolicyStore(context.paths),
        'tmux_cleanup': TmuxCleanupHistoryStore(context.paths),
    }


def _agent_summaries(
    context: CliContext,
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
        latest_snapshot = _latest_snapshot_for_agent(
            context,
            agent_name=agent_name,
            runtime=runtime,
            snapshot_store=stores['snapshot'],
            errors=errors,
        )
        agents.append(
            _agent_summary(
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


def _latest_snapshot_for_agent(
    context: CliContext,
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


def _agent_summary(
    context: CliContext,
    *,
    agent_name: str,
    spec,
    runtime,
    latest_snapshot,
    catalog,
    execution_registry,
) -> dict:
    workspace_path = _workspace_path(context, agent_name=agent_name, runtime=runtime)
    runtime_ref = getattr(runtime, 'runtime_ref', None)
    session_ref = _runtime_session_ref(runtime)
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
        'completion_confidence': _snapshot_confidence(latest_snapshot),
        'last_completion_reason': _snapshot_reason(latest_snapshot),
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


def _workspace_path(context: CliContext, *, agent_name: str, runtime) -> str:
    if runtime is not None and runtime.workspace_path:
        return runtime.workspace_path
    return str(context.paths.workspace_path(agent_name))


def _runtime_session_ref(runtime) -> str | None:
    if runtime is None:
        return None
    return runtime.session_id or runtime.session_ref or runtime.session_file


def _snapshot_confidence(latest_snapshot):
    if latest_snapshot is None or latest_snapshot.latest_decision.confidence is None:
        return None
    return latest_snapshot.latest_decision.confidence.value


def _snapshot_reason(latest_snapshot):
    if latest_snapshot is None:
        return None
    return latest_snapshot.latest_decision.reason


def _ccbd_summary(*, local, stores: dict[str, object], errors: list[str]) -> dict:
    return {
        'state': local.mount_state,
        'pid': None,
        'socket_path': local.socket_path,
        'generation': local.generation,
        'health': local.health,
        'last_heartbeat_at': local.last_heartbeat_at,
        'pid_alive': local.pid_alive,
        'socket_connectable': local.socket_connectable,
        'heartbeat_fresh': local.heartbeat_fresh,
        'takeover_allowed': local.takeover_allowed,
        'reason': local.reason,
        **stores['execution_state'].summary(),
        **_report_summary_fields(_safe_report_load(stores['restore_report'].load, errors, label='restore_report')),
        **_report_summary_fields(_safe_report_load(stores['startup_report'].load, errors, label='startup_report')),
        **_report_summary_fields(_safe_report_load(stores['shutdown_report'].load, errors, label='shutdown_report')),
        **_report_summary_fields(_safe_report_load(stores['namespace_state'].load, errors, label='namespace_state')),
        **_report_summary_fields(_safe_report_load(stores['namespace_event'].load_latest, errors, label='namespace_event')),
        **_report_summary_fields(_safe_report_load(stores['start_policy'].load, errors, label='start_policy')),
        **_report_summary_fields(_safe_report_load(stores['tmux_cleanup'].load_latest, errors, label='tmux_cleanup')),
        'diagnostic_errors': errors,
    }


def _report_summary_fields(report) -> dict:
    if report is None:
        return {}
    return report.summary_fields()


def _safe_report_load(loader, errors: list[str], *, label: str):
    try:
        return loader()
    except Exception as exc:
        errors.append(f'{label}:{exc}')
        return None
