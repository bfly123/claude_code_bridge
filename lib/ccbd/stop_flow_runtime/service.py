from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from agents.models import AgentState
from agents.store import AgentRuntimeStore
from provider_runtime.helper_manifest import clear_helper_manifest
from cli.services.tmux_cleanup_history import TmuxCleanupHistoryStore
from cli.services.tmux_project_cleanup import cleanup_project_tmux_orphans_by_socket
from terminal_runtime.tmux import normalize_socket_name

from .models import StopAllExecution, StopAllSummary
from .pid_cleanup import collect_pid_candidates, terminate_runtime_pids
from .runtime_records import best_effort_runtime, extra_agent_dir_names
from .tmux_cleanup import cleanup_stop_tmux_orphans


def stop_all_project(
    *,
    project_root: Path,
    project_id: str,
    paths,
    registry,
    project_namespace,
    clock,
    force: bool,
    cleanup_project_tmux_orphans_by_socket_fn=cleanup_project_tmux_orphans_by_socket,
    tmux_cleanup_history_store_cls=TmuxCleanupHistoryStore,
) -> StopAllExecution:
    tmux_sockets: set[str | None] = set()
    pid_candidates: dict[int, list[Path]] = {}
    stopped_agents: list[str] = []
    runtime_store = AgentRuntimeStore(paths)
    configured_agent_names = tuple(registry.list_known_agents())
    extra_agent_names = extra_agent_dir_names(paths, configured_agent_names)
    actions_taken: list[str] = []

    if project_namespace is not None:
        namespace_destroy = project_namespace.destroy(reason='stop_all', force=force)
        actions_taken.append(
            'destroy_namespace:'
            f'destroyed={str(namespace_destroy.destroyed).lower()}'
            f',epoch={namespace_destroy.namespace_epoch}'
        )

    for agent_name in (*configured_agent_names, *extra_agent_names):
        runtime = best_effort_runtime(
            agent_name=agent_name,
            configured_agent_names=configured_agent_names,
            registry=registry,
            runtime_store=runtime_store,
        )
        if (
            runtime is not None
            and str(runtime.runtime_ref or '').startswith('tmux:')
            and getattr(runtime, 'tmux_socket_path', None) is None
        ):
            socket_name = normalize_socket_name(runtime.tmux_socket_name)
            if socket_name is not None:
                tmux_sockets.add(socket_name)
        for pid, sources in collect_pid_candidates(
            paths.agent_dir(agent_name),
            runtime=runtime,
            fallback_to_agent_dir=force,
        ).items():
            pid_candidates.setdefault(pid, []).extend(sources)
        if runtime is None or agent_name not in configured_agent_names:
            continue
        registry.upsert_authority(
            replace(
                runtime,
                state=AgentState.STOPPED,
                pid=None,
                runtime_ref=None,
                session_ref=None,
                queue_depth=0,
                socket_path=None,
                health='stopped',
                runtime_pid=None,
                runtime_root=None,
                pane_id=None,
                active_pane_id=None,
                pane_title_marker=None,
                pane_state=None,
                tmux_socket_name=None,
                tmux_socket_path=None,
                session_file=None,
                session_id=None,
                lifecycle_state='stopped',
                desired_state='stopped',
                reconcile_state='stopped',
                last_failure_reason=None,
            )
        )
        stopped_agents.append(agent_name)
        actions_taken.append(f'mark_runtime_stopped:{agent_name}')

    cleanup_summaries = cleanup_stop_tmux_orphans(
        project_id=project_id,
        paths=paths,
        tmux_sockets=tmux_sockets,
        clock=clock,
        actions_taken=actions_taken,
        cleanup_project_tmux_orphans_by_socket_fn=cleanup_project_tmux_orphans_by_socket_fn,
        tmux_cleanup_history_store_cls=tmux_cleanup_history_store_cls,
    )
    terminate_runtime_pids(project_root=project_root, pid_candidates=pid_candidates)
    for agent_name in (*configured_agent_names, *extra_agent_names):
        clear_helper_manifest(paths.agent_helper_path(agent_name))
    actions_taken.append(f'terminate_runtime_pids:{len(pid_candidates)}')
    summary = StopAllSummary(
        project_id=project_id,
        state='unmounted',
        socket_path=str(paths.ccbd_socket_path),
        forced=force,
        stopped_agents=tuple(stopped_agents),
        cleanup_summaries=cleanup_summaries,
    )
    return StopAllExecution(
        summary=summary,
        stopped_agents=tuple(stopped_agents),
        actions_taken=tuple(actions_taken),
        cleanup_summaries=cleanup_summaries,
    )


__all__ = ['stop_all_project']
