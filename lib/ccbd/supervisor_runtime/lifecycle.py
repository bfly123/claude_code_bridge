from __future__ import annotations

from agents.models import build_project_layout_plan

from .namespace import ensure_project_namespace
from .reporting import record_shutdown_report, record_startup_report


def start_supervisor(
    supervisor,
    *,
    agent_names: tuple[str, ...],
    restore: bool,
    auto_permission: bool,
    cleanup_tmux_orphans: bool,
    interactive_tmux_layout: bool,
    recreate_namespace: bool,
    reflow_workspace: bool,
    recreate_reason: str | None,
    run_start_flow_fn,
):
    try:
        namespace_layout_signature = (
            build_project_layout_plan(supervisor._config, requested_agents=agent_names).signature
            if supervisor._project_namespace is not None and interactive_tmux_layout
            else None
        )
        namespace = (
            ensure_project_namespace(
                supervisor._project_namespace,
                layout_signature=namespace_layout_signature,
                recreate_namespace=recreate_namespace,
                reflow_workspace=reflow_workspace,
                recreate_reason=recreate_reason,
            )
            if supervisor._project_namespace is not None
            else None
        )
        namespace_backend_ref = (
            str(getattr(namespace, 'backend_ref', None) or getattr(namespace, 'tmux_socket_path', None) or '').strip()
            if namespace is not None
            else None
        )
        namespace_session_name = (
            str(getattr(namespace, 'session_name', None) or getattr(namespace, 'tmux_session_name', None) or '').strip()
            if namespace is not None
            else None
        )
        namespace_workspace_name = (
            getattr(namespace, 'workspace_name', None) or getattr(namespace, 'workspace_window_name', None)
            if namespace is not None
            else None
        )
        summary = run_start_flow_fn(
            project_root=supervisor._project_root,
            project_id=supervisor._project_id,
            paths=supervisor._paths,
            config=supervisor._config,
            runtime_service=supervisor._runtime_service,
            requested_agents=agent_names,
            restore=restore,
            auto_permission=auto_permission,
            cleanup_tmux_orphans=cleanup_tmux_orphans,
            interactive_tmux_layout=interactive_tmux_layout,
            tmux_socket_path=namespace_backend_ref,
            tmux_session_name=namespace_session_name,
            tmux_workspace_window_name=namespace_workspace_name,
            namespace_epoch=namespace.namespace_epoch if namespace is not None else None,
            workspace_window_id=getattr(namespace, 'workspace_window_id', None) if namespace is not None else None,
            workspace_epoch=getattr(namespace, 'workspace_epoch', None) if namespace is not None else None,
            fresh_namespace=bool(getattr(namespace, 'created_this_call', False)),
            fresh_workspace=bool(getattr(namespace, 'workspace_recreated_this_call', False)),
            clock=supervisor._clock,
        )
    except Exception as exc:
        record_startup_report(
            supervisor,
            requested_agents=agent_names,
            restore=restore,
            auto_permission=auto_permission,
            status='failed',
            actions_taken=('start_flow_failed',),
            cleanup_summaries=(),
            agent_results=(),
            failure_reason=str(exc),
        )
        raise

    record_startup_report(
        supervisor,
        requested_agents=agent_names,
        restore=restore,
        auto_permission=auto_permission,
        status='ok',
        actions_taken=summary.actions_taken,
        cleanup_summaries=summary.cleanup_summaries,
        agent_results=summary.agent_results,
        failure_reason=None,
    )
    return summary


def stop_all_supervisor(
    supervisor,
    *,
    force: bool,
    cleanup_project_tmux_orphans_by_socket_fn,
    tmux_cleanup_history_store_cls,
    stop_all_project_fn,
):
    try:
        execution = stop_all_project_fn(
            project_root=supervisor._project_root,
            project_id=supervisor._project_id,
            paths=supervisor._paths,
            registry=supervisor._registry,
            project_namespace=supervisor._project_namespace,
            clock=supervisor._clock,
            force=force,
            cleanup_project_tmux_orphans_by_socket_fn=cleanup_project_tmux_orphans_by_socket_fn,
            tmux_cleanup_history_store_cls=tmux_cleanup_history_store_cls,
        )
    except Exception as exc:
        record_shutdown_report(
            supervisor,
            trigger='stop_all',
            status='failed',
            forced=force,
            reason='stop_all',
            stopped_agents=(),
            actions_taken=('stop_all_failed',),
            cleanup_summaries=(),
            failure_reason=str(exc),
        )
        raise

    record_shutdown_report(
        supervisor,
        trigger='stop_all',
        status='ok',
        forced=force,
        reason='stop_all',
        stopped_agents=execution.stopped_agents,
        actions_taken=execution.actions_taken,
        cleanup_summaries=execution.cleanup_summaries,
        failure_reason=None,
    )
    try:
        supervisor._start_policy_store.clear()
    except Exception:
        pass
    return execution.summary


__all__ = ['start_supervisor', 'stop_all_supervisor']
