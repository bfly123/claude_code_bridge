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
    runtime_store = AgentRuntimeStore(context.paths)
    snapshot_store = CompletionSnapshotStore(context.paths)
    execution_state_store = ExecutionStateStore(context.paths)
    restore_report_store = CcbdRestoreReportStore(context.paths)
    startup_report_store = CcbdStartupReportStore(context.paths)
    shutdown_report_store = CcbdShutdownReportStore(context.paths)
    namespace_state_store = ProjectNamespaceStateStore(context.paths)
    namespace_event_store = ProjectNamespaceEventStore(context.paths)
    start_policy_store = CcbdStartPolicyStore(context.paths)
    tmux_cleanup_store = TmuxCleanupHistoryStore(context.paths)
    catalog = build_default_provider_catalog()
    execution_registry = build_default_execution_registry()
    local = ping_local_state(context)
    errors: list[str] = []
    agents: list[dict] = []
    for agent_name, spec in sorted(config.agents.items()):
        runtime = runtime_store.load_best_effort(agent_name)
        latest_snapshot = None
        if runtime is not None:
            jobs_path = context.paths.job_store_path(agent_name)
            if jobs_path.exists():
                from jobs.store import JobStore
                try:
                    job_store = JobStore(context.paths)
                    jobs = job_store.list_agent(agent_name)
                    if jobs:
                        latest_snapshot = snapshot_store.load(jobs[-1].job_id)
                except Exception as exc:
                    errors.append(f'job_store:{agent_name}:{exc}')
        workspace_path = runtime.workspace_path if runtime is not None and runtime.workspace_path else str(context.paths.workspace_path(agent_name))
        runtime_ref = runtime.runtime_ref if runtime is not None else None
        session_ref = None
        if runtime is not None:
            session_ref = runtime.session_id or runtime.session_ref or runtime.session_file
        manifest = catalog.resolve_completion_manifest(spec.provider, spec.runtime_mode)
        capability = execution_restore_capability(execution_registry.get(spec.provider), provider=spec.provider)
        agents.append(
            {
                'agent_name': agent_name,
                'provider': spec.provider,
                'runtime_mode': spec.runtime_mode.value,
                'workspace_path': workspace_path,
                'workspace_mode': spec.workspace_mode.value,
                'branch_name': None,
                'completion_family': manifest.completion_family.value,
                'completion_confidence': latest_snapshot.latest_decision.confidence.value if latest_snapshot and latest_snapshot.latest_decision.confidence else None,
                'last_completion_reason': latest_snapshot.latest_decision.reason if latest_snapshot else None,
                'queue_depth': runtime.queue_depth if runtime is not None else 0,
                'health': runtime.health if runtime is not None else 'stopped',
                'runtime_ref': runtime_ref,
                'session_ref': session_ref,
                'backend_type': runtime.backend_type if runtime is not None else spec.runtime_mode.value,
                'binding_status': binding_status(runtime_ref, session_ref, workspace_path),
                'binding_source': runtime.binding_source.value if runtime is not None else 'provider-session',
                'terminal': runtime.terminal_backend if runtime is not None else None,
                'tmux_socket_name': runtime.tmux_socket_name if runtime is not None else None,
                'tmux_socket_path': runtime.tmux_socket_path if runtime is not None else None,
                'pane_id': runtime.pane_id if runtime is not None else None,
                'active_pane_id': runtime.active_pane_id if runtime is not None else None,
                'pane_title_marker': runtime.pane_title_marker if runtime is not None else None,
                'pane_state': runtime.pane_state if runtime is not None else None,
                'execution_resume_supported': capability['resume_supported'],
                'execution_restore_mode': capability['restore_mode'],
                'execution_restore_reason': capability['restore_reason'],
                'execution_restore_detail': capability['restore_detail'],
            }
        )
    restore_report = _safe_report_load(restore_report_store.load, errors, label='restore_report')
    startup_report = _safe_report_load(startup_report_store.load, errors, label='startup_report')
    shutdown_report = _safe_report_load(shutdown_report_store.load, errors, label='shutdown_report')
    namespace_state = _safe_report_load(namespace_state_store.load, errors, label='namespace_state')
    namespace_event = _safe_report_load(namespace_event_store.load_latest, errors, label='namespace_event')
    start_policy = _safe_report_load(start_policy_store.load, errors, label='start_policy')
    cleanup_report = _safe_report_load(tmux_cleanup_store.load_latest, errors, label='tmux_cleanup')
    return {
        'project': str(context.project.project_root),
        'project_id': context.project.project_id,
        'ccbd': {
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
            **execution_state_store.summary(),
            **(restore_report.summary_fields() if restore_report is not None else {}),
            **(startup_report.summary_fields() if startup_report is not None else {}),
            **(shutdown_report.summary_fields() if shutdown_report is not None else {}),
            **(namespace_state.summary_fields() if namespace_state is not None else {}),
            **(namespace_event.summary_fields() if namespace_event is not None else {}),
            **(start_policy.summary_fields() if start_policy is not None else {}),
            **(cleanup_report.summary_fields() if cleanup_report is not None else {}),
            'diagnostic_errors': errors,
        },
        'agents': agents,
    }


def _safe_report_load(loader, errors: list[str], *, label: str):
    try:
        return loader()
    except Exception as exc:
        errors.append(f'{label}:{exc}')
        return None
