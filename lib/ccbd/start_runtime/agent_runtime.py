from __future__ import annotations

from ccbd.models import CcbdStartupAgentResult

from .agent_runtime_binding import resolve_runtime_binding_state
from .agent_runtime_models import StartAgentExecution


def start_agent_runtime(
    *,
    context,
    command,
    runtime_service,
    agent_name: str,
    spec,
    plan,
    binding,
    raw_binding,
    stale_binding: bool,
    assigned_pane_id: str | None,
    style_index: int,
    project_id: str,
    tmux_socket_path: str | None,
    namespace_epoch: int | None,
    ensure_agent_runtime_fn,
    launch_binding_hint_fn,
    relabel_project_namespace_pane_fn,
    same_tmux_socket_path_fn,
    workspace_window_id: str | None = None,
    workspace_epoch: int | None = None,
) -> StartAgentExecution:
    binding_state = resolve_runtime_binding_state(
        context=context,
        command=command,
        agent_name=agent_name,
        spec=spec,
        plan=plan,
        binding=binding,
        raw_binding=raw_binding,
        stale_binding=stale_binding,
        assigned_pane_id=assigned_pane_id,
        style_index=style_index,
        project_id=project_id,
        tmux_socket_path=tmux_socket_path,
        namespace_epoch=namespace_epoch,
        ensure_agent_runtime_fn=ensure_agent_runtime_fn,
        launch_binding_hint_fn=launch_binding_hint_fn,
        relabel_project_namespace_pane_fn=relabel_project_namespace_pane_fn,
        same_tmux_socket_path_fn=same_tmux_socket_path_fn,
    )
    runtime = runtime_service.attach(
        agent_name=agent_name,
        workspace_path=str(plan.workspace_path),
        backend_type=spec.runtime_mode.value,
        runtime_ref=binding_state.runtime_ref,
        session_ref=binding_state.session_ref,
        health=binding_state.health,
        provider=spec.provider,
        runtime_root=getattr(binding_state.binding, 'runtime_root', None),
        runtime_pid=getattr(binding_state.binding, 'runtime_pid', None),
        job_id=getattr(binding_state.binding, 'job_id', None),
        job_owner_pid=getattr(binding_state.binding, 'job_owner_pid', None),
        terminal_backend=getattr(binding_state.binding, 'terminal', None),
        pane_id=getattr(binding_state.binding, 'pane_id', None),
        active_pane_id=getattr(binding_state.binding, 'active_pane_id', None),
        pane_title_marker=getattr(binding_state.binding, 'pane_title_marker', None),
        pane_state=getattr(binding_state.binding, 'pane_state', None),
        tmux_socket_name=getattr(binding_state.binding, 'tmux_socket_name', None),
        tmux_socket_path=getattr(binding_state.binding, 'tmux_socket_path', None),
        session_file=getattr(binding_state.binding, 'session_file', None),
        session_id=getattr(binding_state.binding, 'session_id', None),
        slot_key=agent_name,
        window_id=workspace_window_id,
        workspace_epoch=workspace_epoch,
        lifecycle_state=binding_state.lifecycle_state,
        managed_by='ccbd',
        binding_source='provider-session',
    )

    actions_taken = list(binding_state.actions_taken)
    if command.restore and binding_state.agent_action != 'degraded':
        runtime_service.restore(agent_name)
        actions_taken.append(f'restore_runtime:{agent_name}')

    return StartAgentExecution(
        agent_result=CcbdStartupAgentResult(
            agent_name=agent_name,
            provider=spec.provider,
            action=binding_state.agent_action,
            health=binding_state.health,
            workspace_path=str(plan.workspace_path),
            runtime_ref=runtime.runtime_ref,
            session_ref=runtime.session_ref,
            session_file=runtime.session_file,
            session_id=runtime.session_id,
            lifecycle_state=runtime.lifecycle_state,
            desired_state=runtime.desired_state,
            reconcile_state=runtime.reconcile_state,
            binding_source=runtime.binding_source.value,
            terminal_backend=runtime.terminal_backend,
            tmux_socket_name=runtime.tmux_socket_name,
            tmux_socket_path=runtime.tmux_socket_path,
            pane_id=runtime.pane_id,
            active_pane_id=runtime.active_pane_id,
            pane_state=runtime.pane_state,
            runtime_pid=runtime.runtime_pid,
            runtime_root=runtime.runtime_root,
            job_id=runtime.job_id,
            job_owner_pid=runtime.job_owner_pid,
            failure_reason='stale_binding_unresolved' if binding_state.agent_action == 'degraded' else None,
        ),
        actions_taken=tuple(actions_taken),
        socket_name=binding_state.socket_name,
        runtime_pane_id=binding_state.runtime_pane_id,
        project_socket_active_pane_id=binding_state.project_socket_active_pane_id,
    )


__all__ = ['start_agent_runtime']
