from __future__ import annotations

from pathlib import Path

from .binding import usable_project_binding


def prepare_agents(
    deps,
    *,
    targets,
    config,
    paths,
    context,
    project_root: Path,
    project_id: str,
    tmux_socket_path: str | None,
    tmux_session_name: str | None,
    workspace_window_id: str | None,
):
    return deps.prepare_start_agents_fn(
        targets=targets,
        config=config,
        paths=paths,
        context=context,
        project_root=project_root,
        project_id=project_id,
        tmux_socket_path=tmux_socket_path,
        tmux_session_name=tmux_session_name,
        workspace_window_id=workspace_window_id,
        resolve_agent_binding_fn=deps.resolve_agent_binding_fn,
        project_binding_filter_fn=lambda binding, **kwargs: usable_project_binding(deps, binding, **kwargs),
        restore_state_builder=deps.build_restore_state_impl,
    )


__all__ = ['prepare_agents']
