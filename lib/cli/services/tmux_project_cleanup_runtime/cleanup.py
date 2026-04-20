from __future__ import annotations

from collections.abc import Mapping

from .killing import kill_panes
from .listing import list_project_tmux_panes as list_project_tmux_panes_impl
from .models import ProjectTmuxCleanupSummary


def list_project_tmux_panes(
    *,
    project_id: str,
    socket_name: str | None,
    backend_factory,
    tmux_available_fn,
) -> tuple[str, ...]:
    return list_project_tmux_panes_impl(
        project_id=project_id,
        socket_name=socket_name,
        backend_factory=backend_factory,
        tmux_available_fn=tmux_available_fn,
    )


def cleanup_project_tmux_orphans(
    *,
    project_id: str,
    active_panes: tuple[str, ...],
    socket_name: str | None,
    backend_factory,
    tmux_available_fn,
    current_pane_id: str | None,
) -> tuple[str, ...]:
    active = {str(item).strip() for item in active_panes if str(item).strip().startswith('%')}
    owned = list_project_tmux_panes(
        project_id=project_id,
        socket_name=socket_name,
        backend_factory=backend_factory,
        tmux_available_fn=tmux_available_fn,
    )
    if not owned:
        return ()
    orphaned = tuple(pane for pane in owned if pane not in active)
    if not orphaned:
        return ()
    return kill_panes(
        orphaned,
        socket_name=socket_name,
        backend_factory=backend_factory,
        current_pane_id=current_pane_id,
    )


def cleanup_project_tmux_orphans_by_socket(
    *,
    project_id: str,
    active_panes_by_socket: Mapping[str | None, tuple[str, ...]],
    backend_factory,
    tmux_available_fn,
    current_pane_id: str | None,
) -> tuple[ProjectTmuxCleanupSummary, ...]:
    summaries: list[ProjectTmuxCleanupSummary] = []
    socket_names: list[str | None] = list(active_panes_by_socket)
    if None not in active_panes_by_socket:
        socket_names.append(None)
    for socket_name in socket_names:
        owned = list_project_tmux_panes(
            project_id=project_id,
            socket_name=socket_name,
            backend_factory=backend_factory,
            tmux_available_fn=tmux_available_fn,
        )
        if not owned:
            continue
        active = tuple(
            pane for pane in dict.fromkeys(active_panes_by_socket.get(socket_name, ()))
            if str(pane).strip().startswith('%')
        )
        orphaned = tuple(pane for pane in owned if pane not in set(active))
        killed = (
            kill_panes(
                orphaned,
                socket_name=socket_name,
                backend_factory=backend_factory,
                current_pane_id=current_pane_id,
            )
            if orphaned
            else ()
        )
        summaries.append(
            ProjectTmuxCleanupSummary(
                socket_name=socket_name,
                owned_panes=owned,
                active_panes=active,
                orphaned_panes=orphaned,
                killed_panes=killed,
            )
        )
    return tuple(summaries)


def kill_project_tmux_panes(
    *,
    project_id: str,
    socket_name: str | None,
    backend_factory,
    tmux_available_fn,
    current_pane_id: str | None,
) -> tuple[str, ...]:
    unique_panes = list(
        list_project_tmux_panes(
            project_id=project_id,
            socket_name=socket_name,
            backend_factory=backend_factory,
            tmux_available_fn=tmux_available_fn,
        )
    )
    if not unique_panes:
        return ()

    return kill_panes(
        unique_panes,
        socket_name=socket_name,
        backend_factory=backend_factory,
        current_pane_id=current_pane_id,
    )


__all__ = [
    'ProjectTmuxCleanupSummary',
    'cleanup_project_tmux_orphans',
    'cleanup_project_tmux_orphans_by_socket',
    'kill_project_tmux_panes',
    'list_project_tmux_panes',
]
