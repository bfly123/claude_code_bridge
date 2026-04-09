from __future__ import annotations

from .agent_runtime_models import RuntimeBindingState


def resolve_runtime_binding_state(
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
    binding, agent_action = launch_or_reuse_binding(
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
        relabel_runtime_pane(
            binding=binding,
            agent_name=agent_name,
            project_id=project_id,
            style_index=style_index,
            tmux_socket_path=tmux_socket_path,
            namespace_epoch=namespace_epoch,
            relabel_project_namespace_pane_fn=relabel_project_namespace_pane_fn,
        )
    )
    runtime_ref, session_ref, health, lifecycle_state, agent_action = runtime_status(
        binding=binding,
        stale_binding=stale_binding,
        agent_name=agent_name,
        agent_action=agent_action,
        actions_taken=actions_taken,
    )
    socket_name, runtime_pane_id, project_socket_active_pane_id = runtime_pane_facts(
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


def launch_or_reuse_binding(
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


def relabel_runtime_pane(
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


def runtime_status(
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
    actions_taken.extend(runtime_action_markers(agent_name=agent_name, agent_action=agent_action))
    return runtime_ref, session_ref, 'healthy', 'idle', agent_action


def runtime_action_markers(*, agent_name: str, agent_action: str) -> tuple[str, ...]:
    mapping = {
        'attached': f'reuse_binding:{agent_name}',
        'launched': f'launch_runtime:{agent_name}',
        'relaunched': f'relaunch_runtime:{agent_name}',
    }
    marker = mapping.get(agent_action)
    return (marker,) if marker else ()


def runtime_pane_facts(
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


__all__ = ['resolve_runtime_binding_state']
