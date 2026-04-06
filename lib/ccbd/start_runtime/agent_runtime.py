from __future__ import annotations

from dataclasses import dataclass

from ccbd.models import CcbdStartupAgentResult


@dataclass(frozen=True)
class StartAgentExecution:
    agent_result: CcbdStartupAgentResult
    actions_taken: tuple[str, ...]
    socket_name: str | None
    runtime_pane_id: str | None
    project_socket_active_pane_id: str | None


@dataclass(frozen=True)
class RuntimeBindingState:
    binding: object | None
    agent_action: str
    actions_taken: tuple[str, ...]
    runtime_ref: str | None
    session_ref: str | None
    health: str
    lifecycle_state: str
    socket_name: str | None
    runtime_pane_id: str | None
    project_socket_active_pane_id: str | None


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
) -> StartAgentExecution:
    binding_state = _resolve_runtime_binding_state(
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
        terminal_backend=getattr(binding_state.binding, 'terminal', None),
        pane_id=getattr(binding_state.binding, 'pane_id', None),
        active_pane_id=getattr(binding_state.binding, 'active_pane_id', None),
        pane_title_marker=getattr(binding_state.binding, 'pane_title_marker', None),
        pane_state=getattr(binding_state.binding, 'pane_state', None),
        tmux_socket_name=getattr(binding_state.binding, 'tmux_socket_name', None),
        tmux_socket_path=getattr(binding_state.binding, 'tmux_socket_path', None),
        session_file=getattr(binding_state.binding, 'session_file', None),
        session_id=getattr(binding_state.binding, 'session_id', None),
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
            failure_reason='stale_binding_unresolved' if binding_state.agent_action == 'degraded' else None,
        ),
        actions_taken=tuple(actions_taken),
        socket_name=binding_state.socket_name,
        runtime_pane_id=binding_state.runtime_pane_id,
        project_socket_active_pane_id=binding_state.project_socket_active_pane_id,
    )


def _resolve_runtime_binding_state(
    *,
    context,
    command,
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
) -> RuntimeBindingState:
    binding, agent_action = _launch_or_reuse_binding(
        context=context,
        command=command,
        spec=spec,
        plan=plan,
        binding=binding,
        raw_binding=raw_binding,
        stale_binding=stale_binding,
        assigned_pane_id=assigned_pane_id,
        style_index=style_index,
        tmux_socket_path=tmux_socket_path,
        ensure_agent_runtime_fn=ensure_agent_runtime_fn,
        launch_binding_hint_fn=launch_binding_hint_fn,
    )
    actions_taken: list[str] = []
    actions_taken.extend(
        _relabel_runtime_pane(
            binding=binding,
            agent_name=agent_name,
            project_id=project_id,
            style_index=style_index,
            tmux_socket_path=tmux_socket_path,
            namespace_epoch=namespace_epoch,
            relabel_project_namespace_pane_fn=relabel_project_namespace_pane_fn,
        )
    )
    runtime_ref, session_ref, health, lifecycle_state, agent_action = _runtime_status(
        binding=binding,
        stale_binding=stale_binding,
        agent_name=agent_name,
        agent_action=agent_action,
        actions_taken=actions_taken,
    )
    socket_name, runtime_pane_id, project_socket_active_pane_id = _runtime_pane_facts(
        binding=binding,
        runtime_ref=runtime_ref,
        tmux_socket_path=tmux_socket_path,
        same_tmux_socket_path_fn=same_tmux_socket_path_fn,
    )
    return RuntimeBindingState(
        binding=binding,
        agent_action=agent_action,
        actions_taken=tuple(actions_taken),
        runtime_ref=runtime_ref,
        session_ref=session_ref,
        health=health,
        lifecycle_state=lifecycle_state,
        socket_name=socket_name,
        runtime_pane_id=runtime_pane_id,
        project_socket_active_pane_id=project_socket_active_pane_id,
    )


def _launch_or_reuse_binding(
    *,
    context,
    command,
    spec,
    plan,
    binding,
    raw_binding,
    stale_binding: bool,
    assigned_pane_id: str | None,
    style_index: int,
    tmux_socket_path: str | None,
    ensure_agent_runtime_fn,
    launch_binding_hint_fn,
):
    if binding is not None:
        return binding, 'attached'

    launch = ensure_agent_runtime_fn(
        context,
        command,
        spec,
        plan,
        launch_binding_hint_fn(
            binding=binding,
            raw_binding=raw_binding,
            stale_binding=stale_binding,
            assigned_pane_id=assigned_pane_id,
            tmux_socket_path=tmux_socket_path,
        ),
        assigned_pane_id=assigned_pane_id,
        style_index=style_index,
        tmux_socket_path=tmux_socket_path,
    )
    binding = launch.binding
    if stale_binding and launch.launched:
        return binding, 'relaunched'
    if launch.launched:
        return binding, 'launched'
    return binding, 'attached'


def _relabel_runtime_pane(
    *,
    binding,
    agent_name: str,
    project_id: str,
    style_index: int,
    tmux_socket_path: str | None,
    namespace_epoch: int | None,
    relabel_project_namespace_pane_fn,
) -> tuple[str, ...]:
    if binding is None:
        return ()
    relabeled_pane = relabel_project_namespace_pane_fn(
        binding=binding,
        agent_name=agent_name,
        project_id=project_id,
        style_index=style_index,
        tmux_socket_path=tmux_socket_path,
        namespace_epoch=namespace_epoch,
    )
    if relabeled_pane is None:
        return ()
    return (f'relabel_runtime_pane:{agent_name}:{relabeled_pane}',)


def _runtime_status(
    *,
    binding,
    stale_binding: bool,
    agent_name: str,
    agent_action: str,
    actions_taken: list[str],
) -> tuple[str | None, str | None, str, str, str]:
    if binding is None and stale_binding:
        actions_taken.append(f'degraded_stale_binding:{agent_name}')
        return '', '', 'degraded', 'degraded', 'degraded'

    runtime_ref = binding.runtime_ref if binding else None
    session_ref = binding.session_ref if binding else None
    actions_taken.extend(_runtime_action_markers(agent_name=agent_name, agent_action=agent_action))
    return runtime_ref, session_ref, 'healthy', 'idle', agent_action


def _runtime_action_markers(*, agent_name: str, agent_action: str) -> tuple[str, ...]:
    mapping = {
        'attached': f'reuse_binding:{agent_name}',
        'launched': f'launch_runtime:{agent_name}',
        'relaunched': f'relaunch_runtime:{agent_name}',
    }
    marker = mapping.get(agent_action)
    return (marker,) if marker else ()


def _runtime_pane_facts(
    *,
    binding,
    runtime_ref: str | None,
    tmux_socket_path: str | None,
    same_tmux_socket_path_fn,
) -> tuple[str | None, str | None, str | None]:
    if not runtime_ref or not str(runtime_ref).startswith('tmux:') or binding is None:
        return None, None, None
    runtime_pane_id = str(runtime_ref)[len('tmux:') :]
    socket_name = binding.tmux_socket_path or binding.tmux_socket_name
    project_socket_active_pane_id = None
    if same_tmux_socket_path_fn(getattr(binding, 'tmux_socket_path', None), tmux_socket_path):
        project_socket_active_pane_id = runtime_pane_id
    return socket_name, runtime_pane_id, project_socket_active_pane_id


__all__ = ['start_agent_runtime']
