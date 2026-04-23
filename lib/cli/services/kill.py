from __future__ import annotations

from dataclasses import replace
from ccbd.services.project_namespace import ProjectNamespaceController
from ccbd.services.start_policy import CcbdStartPolicyStore
from ccbd.system import utc_now
from ccbd.socket_client import CcbdClient
from cli.context import CliContext
from cli.services.kill_runtime.agent_cleanup import (
    extra_agent_dir_names as _extra_agent_dir_names_impl,
    prepare_local_shutdown as _prepare_local_shutdown_impl,
)
from cli.services.kill_runtime.finalize import finalize_kill as _finalize_kill_impl
from cli.services.kill_runtime.lifecycle import destroy_project_namespace as _destroy_project_namespace_impl
from cli.services.kill_runtime.pid_cleanup import (
    LocalProcessTreeOwner,
    WindowsJobMetadataProcessTreeOwnerFactory,
    collect_agent_pid_candidates as _collect_agent_pid_candidates_impl,
    collect_project_process_candidates as _collect_project_process_candidates_impl,
    path_within as _path_within_impl,
    pid_matches_project as _pid_matches_project_impl,
    read_proc_cmdline as _read_proc_cmdline_impl,
    read_proc_path as _read_proc_path_impl,
    remove_pid_files as _remove_pid_files_impl,
    terminate_runtime_pids as _terminate_runtime_pids_impl,
)
from cli.services.kill_runtime.remote import (
    await_remote_shutdown as _await_remote_shutdown_impl,
    request_remote_stop as _request_remote_stop_impl,
    resolve_shutdown_summary as _resolve_shutdown_summary_impl,
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
from workspace.git_worktree import prune_missing_worktrees_under
from workspace.reconcile import inspect_kill_worktrees

_STOP_ALL_TIMEOUT_S = 12.0


def kill_project(context: CliContext, command: ParsedKillCommand):
    remote_summary = _request_remote_stop(context, force=command.force)
    preparation = _prepare_local_shutdown(context, force=command.force)
    _destroy_project_namespace(context, force=command.force)
    summary = _resolve_shutdown_summary(context, remote_summary=remote_summary, force=command.force)
    final_summary = _finalize_kill(
        context,
        force=command.force,
        preparation=preparation,
        remote_summary=remote_summary,
        summary=summary,
    )
    if command.force:
        try:
            prune_missing_worktrees_under(context.project.project_root, context.paths.workspaces_dir)
        except Exception:
            pass
    guard_summary = inspect_kill_worktrees(context.project.project_root)
    if not guard_summary.warnings:
        return final_summary
    return replace(final_summary, worktree_warnings=tuple(guard_summary.warnings))


def _request_remote_stop(context: CliContext, *, force: bool) -> KillSummary | None:
    return _request_remote_stop_impl(
        context,
        force=force,
        connect_mounted_daemon_fn=connect_mounted_daemon,
        record_shutdown_intent_fn=record_shutdown_intent,
        ccbd_client_cls=CcbdClient,
        summary_from_stop_all_payload_fn=_summary_from_stop_all_payload,
        stop_all_timeout_s=_STOP_ALL_TIMEOUT_S,
        service_error_cls=CcbdServiceError,
    )


def _prepare_local_shutdown(context: CliContext, *, force: bool):
    return _prepare_local_shutdown_impl(
        context,
        force=force,
        collect_agent_pid_candidates_fn=_collect_agent_pid_candidates,
    )


def _destroy_project_namespace(context: CliContext, *, force: bool) -> None:
    _destroy_project_namespace_impl(
        context,
        force=force,
        project_namespace_controller_cls=ProjectNamespaceController,
        start_policy_store_cls=CcbdStartPolicyStore,
    )


def _resolve_shutdown_summary(context: CliContext, *, remote_summary: KillSummary | None, force: bool) -> KillSummary:
    return _resolve_shutdown_summary_impl(
        context,
        remote_summary=remote_summary,
        force=force,
        shutdown_daemon_fn=shutdown_daemon,
        await_remote_shutdown_fn=_await_remote_shutdown,
        service_error_cls=CcbdServiceError,
        kill_summary_cls=KillSummary,
    )


def _finalize_kill(
    context: CliContext,
    *,
    force: bool,
    preparation,
    remote_summary: KillSummary | None,
    summary: KillSummary,
) -> KillSummary:
    return _finalize_kill_impl(
        context,
        force=force,
        preparation=preparation,
        remote_summary=remote_summary,
        summary=summary,
        set_tmux_ui_active_fn=set_tmux_ui_active,
        cleanup_project_tmux_orphans_by_socket_fn=cleanup_project_tmux_orphans_by_socket,
        terminate_runtime_pids_fn=_terminate_runtime_pids,
        tmux_cleanup_history_store_cls=TmuxCleanupHistoryStore,
        tmux_cleanup_event_cls=TmuxCleanupEvent,
        merge_cleanup_summaries_fn=_merge_cleanup_summaries,
        record_kill_report_fn=_record_kill_report,
        kill_summary_cls=KillSummary,
        clock_fn=utc_now,
    )


def _await_remote_shutdown(context: CliContext, *, force: bool, timeout_s: float = 2.5) -> KillSummary:
    return _await_remote_shutdown_impl(
        context,
        force=force,
        inspect_daemon_fn=inspect_daemon,
        lease_health_cls=LeaseHealth,
        kill_summary_cls=KillSummary,
        timeout_s=timeout_s,
    )


_summary_from_stop_all_payload = _summary_from_stop_all_payload_impl
_merge_cleanup_summaries = _merge_cleanup_summaries_impl
_extra_agent_dir_names = _extra_agent_dir_names_impl
_collect_agent_pid_candidates = _collect_agent_pid_candidates_impl
_read_proc_path = _read_proc_path_impl
_read_proc_cmdline = _read_proc_cmdline_impl
_path_within = _path_within_impl
_remove_pid_files = _remove_pid_files_impl


def _terminate_runtime_pids(*, project_root, pid_candidates, priority_pids=(), pid_metadata=None) -> None:
    local_owner = LocalProcessTreeOwner(terminate_pid_tree)
    _terminate_runtime_pids_impl(
        project_root=project_root,
        pid_candidates=pid_candidates,
        priority_pids=priority_pids,
        pid_metadata=pid_metadata,
        is_pid_alive_fn=is_pid_alive,
        pid_matches_project_fn=_pid_matches_project,
        process_tree_owner=local_owner,
        process_tree_owner_factory=WindowsJobMetadataProcessTreeOwnerFactory(local_owner, is_windows_fn=lambda: True),
        remove_pid_files_fn=_remove_pid_files,
        collect_project_process_candidates_fn=_collect_project_process_candidates_impl,
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
