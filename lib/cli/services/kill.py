from __future__ import annotations

import time

from ccbd.services.project_namespace import ProjectNamespaceController
from ccbd.services.start_policy import CcbdStartPolicyStore
from ccbd.system import utc_now
from ccbd.socket_client import CcbdClient
from cli.context import CliContext
from cli.services.kill_runtime.agent_cleanup import (
    extra_agent_dir_names as _extra_agent_dir_names_impl,
    prepare_local_shutdown as _prepare_local_shutdown_impl,
)
from cli.services.kill_runtime.pid_cleanup import (
    collect_agent_pid_candidates as _collect_agent_pid_candidates_impl,
    path_within as _path_within_impl,
    pid_matches_project as _pid_matches_project_impl,
    read_proc_cmdline as _read_proc_cmdline_impl,
    read_proc_path as _read_proc_path_impl,
    remove_pid_files as _remove_pid_files_impl,
    terminate_runtime_pids as _terminate_runtime_pids_impl,
)
from cli.services.kill_runtime.reporting import (
    merge_cleanup_summaries as _merge_cleanup_summaries_impl,
    record_kill_report as _record_kill_report_impl,
    summary_from_stop_all_payload as _summary_from_stop_all_payload_impl,
)
from cli.kill_runtime.processes import is_pid_alive, terminate_pid_tree
from cli.models import ParsedKillCommand
from ccbd.models import LeaseHealth

from .daemon import CcbdServiceError, KillSummary, connect_mounted_daemon, inspect_daemon, record_shutdown_intent, shutdown_daemon
from .tmux_cleanup_history import TmuxCleanupEvent, TmuxCleanupHistoryStore
from .tmux_project_cleanup import ProjectTmuxCleanupSummary, cleanup_project_tmux_orphans_by_socket
from .tmux_ui import set_tmux_ui_active

_STOP_ALL_TIMEOUT_S = 12.0


def kill_project(context: CliContext, command: ParsedKillCommand):
    remote_summary = _request_remote_stop(context, force=command.force)
    preparation = _prepare_local_shutdown(context, force=command.force)
    _destroy_project_namespace(context, force=command.force)
    summary = _resolve_shutdown_summary(context, remote_summary=remote_summary, force=command.force)
    return _finalize_kill(
        context,
        force=command.force,
        preparation=preparation,
        remote_summary=remote_summary,
        summary=summary,
    )


def _request_remote_stop(context: CliContext, *, force: bool) -> KillSummary | None:
    try:
        handle = connect_mounted_daemon(context, allow_restart_stale=False)
    except CcbdServiceError:
        return None
    if handle is None or handle.client is None:
        return None
    try:
        record_shutdown_intent(context, reason='kill')
        stop_all_client = (
            CcbdClient(context.paths.ccbd_socket_path, timeout_s=_STOP_ALL_TIMEOUT_S)
            if isinstance(handle.client, CcbdClient)
            else handle.client
        )
        payload = stop_all_client.stop_all(force=force)
    except Exception:
        if not force:
            raise
        return None
    return _summary_from_stop_all_payload(payload)


def _prepare_local_shutdown(context: CliContext, *, force: bool):
    return _prepare_local_shutdown_impl(
        context,
        force=force,
        collect_agent_pid_candidates_fn=_collect_agent_pid_candidates,
    )


def _destroy_project_namespace(context: CliContext, *, force: bool) -> None:
    ProjectNamespaceController(context.paths, context.project.project_id).destroy(
        reason='kill',
        force=force,
    )
    try:
        CcbdStartPolicyStore(context.paths).clear()
    except Exception:
        pass


def _resolve_shutdown_summary(context: CliContext, *, remote_summary: KillSummary | None, force: bool) -> KillSummary:
    if remote_summary is not None:
        return _await_remote_shutdown(context, force=force)
    try:
        return shutdown_daemon(context, force=force)
    except CcbdServiceError:
        if not force:
            raise
        return KillSummary(
            project_id=context.project.project_id,
            state='unmounted',
            socket_path=str(context.paths.ccbd_socket_path),
            forced=force,
        )


def _finalize_kill(
    context: CliContext,
    *,
    force: bool,
    preparation,
    remote_summary: KillSummary | None,
    summary: KillSummary,
) -> KillSummary:
    set_tmux_ui_active(False)
    cleanup_summaries = cleanup_project_tmux_orphans_by_socket(
        project_id=context.project.project_id,
        active_panes_by_socket={socket_name: () for socket_name in preparation.tmux_sockets},
    )
    _terminate_runtime_pids(
        project_root=context.project.project_root,
        pid_candidates=preparation.pid_candidates,
    )
    if cleanup_summaries:
        TmuxCleanupHistoryStore(context.paths).append(
            TmuxCleanupEvent(
                event_kind='kill',
                project_id=context.project.project_id,
                occurred_at=utc_now(),
                summaries=cleanup_summaries,
            )
        )
    all_cleanup_summaries = _merge_cleanup_summaries(
        remote_summary.cleanup_summaries if remote_summary is not None else (),
        cleanup_summaries,
    )
    final_summary = KillSummary(
        project_id=(remote_summary or summary).project_id,
        state=summary.state,
        socket_path=summary.socket_path,
        forced=force,
        cleanup_summaries=all_cleanup_summaries,
    )
    _record_kill_report(
        context,
        trigger='kill' if remote_summary is not None else 'kill_fallback',
        forced=force,
        cleanup_summaries=all_cleanup_summaries,
    )
    return final_summary


def _await_remote_shutdown(context: CliContext, *, force: bool, timeout_s: float = 2.5) -> KillSummary:
    deadline = time.time() + max(0.1, float(timeout_s))
    last_inspection = None
    while time.time() < deadline:
        _, _, inspection = inspect_daemon(context)
        last_inspection = inspection
        if not inspection.socket_connectable and inspection.health in {LeaseHealth.MISSING, LeaseHealth.UNMOUNTED, LeaseHealth.STALE}:
            break
        time.sleep(0.05)
    lease = None if last_inspection is None else last_inspection.lease
    return KillSummary(
        project_id=context.project.project_id,
        state=lease.mount_state.value if lease is not None else 'unmounted',
        socket_path=str(context.paths.ccbd_socket_path),
        forced=force,
    )


def _summary_from_stop_all_payload(payload: dict) -> KillSummary:
    return _summary_from_stop_all_payload_impl(payload)


def _merge_cleanup_summaries(*groups: tuple[ProjectTmuxCleanupSummary, ...]) -> tuple[ProjectTmuxCleanupSummary, ...]:
    return _merge_cleanup_summaries_impl(*groups)


def _extra_agent_dir_names(context: CliContext, configured_agent_names: tuple[str, ...]) -> tuple[str, ...]:
    return _extra_agent_dir_names_impl(context, configured_agent_names)


def _collect_agent_pid_candidates(
    agent_dir,
    *,
    runtime,
    fallback_to_agent_dir: bool,
) -> dict[int, list]:
    return _collect_agent_pid_candidates_impl(
        agent_dir=agent_dir,
        runtime=runtime,
        fallback_to_agent_dir=fallback_to_agent_dir,
    )


def _terminate_runtime_pids(*, project_root, pid_candidates) -> None:
    _terminate_runtime_pids_impl(
        project_root=project_root,
        pid_candidates=pid_candidates,
        is_pid_alive_fn=is_pid_alive,
        pid_matches_project_fn=_pid_matches_project,
        terminate_pid_tree_fn=terminate_pid_tree,
        remove_pid_files_fn=_remove_pid_files,
    )


def _record_kill_report(
    context: CliContext,
    *,
    trigger: str,
    forced: bool,
    cleanup_summaries: tuple[ProjectTmuxCleanupSummary, ...],
) -> None:
    _record_kill_report_impl(
        context,
        trigger=trigger,
        forced=forced,
        cleanup_summaries=cleanup_summaries,
        extra_agent_dir_names_fn=_extra_agent_dir_names,
    )


def _pid_matches_project(pid: int, *, project_root, hint_paths) -> bool:
    return _pid_matches_project_impl(
        pid,
        project_root=project_root,
        hint_paths=hint_paths,
        read_proc_path_fn=_read_proc_path,
        read_proc_cmdline_fn=_read_proc_cmdline,
        path_within_fn=_path_within,
    )


def _read_proc_path(pid: int, entry: str):
    return _read_proc_path_impl(pid, entry)


def _read_proc_cmdline(pid: int) -> str:
    return _read_proc_cmdline_impl(pid)


def _path_within(path, root) -> bool:
    return _path_within_impl(path, root)


def _remove_pid_files(paths) -> None:
    _remove_pid_files_impl(paths)
