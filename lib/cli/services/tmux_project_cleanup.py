from __future__ import annotations

import os
import shutil

from terminal_runtime import TmuxBackend
from .tmux_project_cleanup_runtime import (
    ProjectTmuxCleanupSummary,
    cleanup_project_tmux_orphans as cleanup_project_tmux_orphans_impl,
    cleanup_project_tmux_orphans_by_socket as cleanup_project_tmux_orphans_by_socket_impl,
    kill_project_tmux_panes as kill_project_tmux_panes_impl,
    list_project_tmux_panes as list_project_tmux_panes_impl,
)

def list_project_tmux_panes(
    *,
    project_id: str,
    socket_name: str | None = None,
    backend_factory=TmuxBackend,
) -> tuple[str, ...]:
    return list_project_tmux_panes_impl(
        project_id=project_id,
        socket_name=socket_name,
        backend_factory=backend_factory,
        tmux_available_fn=shutil.which,
    )


def cleanup_project_tmux_orphans(
    *,
    project_id: str,
    active_panes: tuple[str, ...] = (),
    socket_name: str | None = None,
    backend_factory=TmuxBackend,
) -> tuple[str, ...]:
    return cleanup_project_tmux_orphans_impl(
        project_id=project_id,
        active_panes=active_panes,
        socket_name=socket_name,
        backend_factory=backend_factory,
        tmux_available_fn=shutil.which,
        current_pane_id=os.environ.get('TMUX_PANE'),
    )


def cleanup_project_tmux_orphans_by_socket(
    *,
    project_id: str,
    active_panes_by_socket,
    backend_factory=TmuxBackend,
) -> tuple[ProjectTmuxCleanupSummary, ...]:
    return cleanup_project_tmux_orphans_by_socket_impl(
        project_id=project_id,
        active_panes_by_socket=active_panes_by_socket,
        backend_factory=backend_factory,
        tmux_available_fn=shutil.which,
        current_pane_id=os.environ.get('TMUX_PANE'),
    )


def kill_project_tmux_panes(
    *,
    project_id: str,
    socket_name: str | None = None,
    backend_factory=TmuxBackend,
) -> tuple[str, ...]:
    return kill_project_tmux_panes_impl(
        project_id=project_id,
        socket_name=socket_name,
        backend_factory=backend_factory,
        tmux_available_fn=shutil.which,
        current_pane_id=os.environ.get('TMUX_PANE'),
    )


__all__ = [
    'ProjectTmuxCleanupSummary',
    'cleanup_project_tmux_orphans',
    'cleanup_project_tmux_orphans_by_socket',
    'kill_project_tmux_panes',
    'list_project_tmux_panes',
]
