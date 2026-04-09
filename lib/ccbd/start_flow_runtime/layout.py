from __future__ import annotations

from cli.services.tmux_cleanup_history import TmuxCleanupHistoryStore
from cli.services.tmux_project_cleanup import ProjectTmuxCleanupSummary
from cli.services.tmux_start_layout import TmuxStartLayout


def prepare_start_layout(
    deps,
    context,
    *,
    config,
    targets: tuple[str, ...],
    layout_plan=None,
    tmux_backend=None,
    root_pane_id: str | None = None,
) -> TmuxStartLayout:
    return deps.prepare_start_layout_impl(
        context,
        config=config,
        targets=targets,
        layout_plan=layout_plan,
        tmux_backend=tmux_backend,
        root_pane_id=root_pane_id,
        inside_tmux_fn=deps.inside_tmux_impl,
        prepare_tmux_start_layout_fn=deps.prepare_tmux_start_layout_fn,
    )


def session_root_pane(
    deps,
    backend,
    session_name: str | None,
    *,
    workspace_window_name: str | None = None,
) -> str | None:
    return deps.session_root_pane_impl(
        backend,
        session_name,
        workspace_window_name=workspace_window_name,
    )


def cleanup_start_tmux_orphans(
    deps,
    *,
    project_id: str,
    paths,
    active_panes_by_socket: dict[str | None, list[str]],
    project_socket_active_panes: list[str],
    tmux_socket_path: str | None,
    clock,
) -> tuple[ProjectTmuxCleanupSummary, ...]:
    return deps.cleanup_start_tmux_orphans_impl(
        project_id=project_id,
        paths=paths,
        active_panes_by_socket=active_panes_by_socket,
        project_socket_active_panes=project_socket_active_panes,
        tmux_socket_path=tmux_socket_path,
        clock=clock,
        cleanup_project_tmux_orphans_by_socket_fn=deps.cleanup_project_tmux_orphans_by_socket_fn,
        tmux_cleanup_history_store_cls=deps.tmux_cleanup_history_store_cls or TmuxCleanupHistoryStore,
    )


__all__ = ['cleanup_start_tmux_orphans', 'prepare_start_layout', 'session_root_pane']
