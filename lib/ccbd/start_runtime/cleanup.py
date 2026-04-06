from __future__ import annotations

from cli.services.tmux_cleanup_history import TmuxCleanupEvent
from cli.services.tmux_project_cleanup import ProjectTmuxCleanupSummary


def cleanup_start_tmux_orphans(
    *,
    project_id: str,
    paths,
    active_panes_by_socket: dict[str | None, list[str]],
    project_socket_active_panes: list[str],
    tmux_socket_path: str | None,
    clock,
    cleanup_project_tmux_orphans_by_socket_fn,
    tmux_cleanup_history_store_cls,
) -> tuple[ProjectTmuxCleanupSummary, ...]:
    active_by_socket = {key: tuple(dict.fromkeys(value)) for key, value in active_panes_by_socket.items()}
    if tmux_socket_path is not None:
        active_by_socket[tmux_socket_path] = tuple(
            pane_id
            for pane_id in dict.fromkeys(project_socket_active_panes)
            if str(pane_id).strip().startswith('%')
        )
    cleanup_summaries = cleanup_project_tmux_orphans_by_socket_fn(
        project_id=project_id,
        active_panes_by_socket=active_by_socket,
    )
    tmux_cleanup_history_store_cls(paths).append(
        TmuxCleanupEvent(
            event_kind='start',
            project_id=project_id,
            occurred_at=clock(),
            summaries=cleanup_summaries,
        )
    )
    return cleanup_summaries
