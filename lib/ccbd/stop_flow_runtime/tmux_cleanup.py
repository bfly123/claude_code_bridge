from __future__ import annotations

from cli.services.tmux_cleanup_history import TmuxCleanupEvent


def cleanup_stop_tmux_orphans(
    *,
    project_id: str,
    paths,
    tmux_sockets: set[str | None],
    clock,
    actions_taken: list[str],
    cleanup_project_tmux_orphans_by_socket_fn,
    tmux_cleanup_history_store_cls,
):
    if not tmux_sockets:
        actions_taken.append('cleanup_tmux_orphans:skipped')
        return ()
    cleanup_summaries = cleanup_project_tmux_orphans_by_socket_fn(
        project_id=project_id,
        active_panes_by_socket={socket_name: () for socket_name in tmux_sockets},
    )
    total_killed = sum(len(item.killed_panes) for item in cleanup_summaries)
    actions_taken.append(f'cleanup_tmux_orphans:killed={total_killed}')
    tmux_cleanup_history_store_cls(paths).append(
        TmuxCleanupEvent(
            event_kind='kill',
            project_id=project_id,
            occurred_at=clock(),
            summaries=cleanup_summaries,
        )
    )
    return cleanup_summaries


__all__ = ['cleanup_stop_tmux_orphans']
