from __future__ import annotations

from provider_runtime.helper_manifest import clear_helper_manifest


def finalize_kill(
    context,
    *,
    force: bool,
    preparation,
    remote_summary,
    summary,
    set_tmux_ui_active_fn,
    cleanup_project_tmux_orphans_by_socket_fn,
    terminate_runtime_pids_fn,
    tmux_cleanup_history_store_cls,
    tmux_cleanup_event_cls,
    merge_cleanup_summaries_fn,
    record_kill_report_fn,
    kill_summary_cls,
    clock_fn,
):
    set_tmux_ui_active_fn(False)
    cleanup_summaries = cleanup_project_tmux_orphans_by_socket_fn(
        project_id=context.project.project_id,
        active_panes_by_socket={socket_name: () for socket_name in preparation.tmux_sockets},
    )
    terminate_runtime_pids_fn(
        project_root=context.project.project_root,
        pid_candidates=preparation.pid_candidates,
    )
    for agent_name in (*preparation.configured_agent_names, *preparation.extra_agent_names):
        clear_helper_manifest(context.paths.agent_helper_path(agent_name))
    if cleanup_summaries:
        tmux_cleanup_history_store_cls(context.paths).append(
            tmux_cleanup_event_cls(
                event_kind='kill',
                project_id=context.project.project_id,
                occurred_at=clock_fn(),
                summaries=cleanup_summaries,
            )
        )
    all_cleanup_summaries = merge_cleanup_summaries_fn(
        remote_summary.cleanup_summaries if remote_summary is not None else (),
        cleanup_summaries,
    )
    final_summary = kill_summary_cls(
        project_id=(remote_summary or summary).project_id,
        state=summary.state,
        socket_path=summary.socket_path,
        forced=force,
        cleanup_summaries=all_cleanup_summaries,
    )
    record_kill_report_fn(
        context,
        trigger='kill' if remote_summary is not None else 'kill_fallback',
        forced=force,
        cleanup_summaries=all_cleanup_summaries,
    )
    return final_summary


__all__ = ['finalize_kill']
