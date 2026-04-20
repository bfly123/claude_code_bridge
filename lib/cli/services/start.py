from __future__ import annotations

from dataclasses import replace

from agents.config_loader import load_project_config
from ccbd.lifecycle_report_store import CcbdStartupReportStore

from .daemon import ensure_daemon_started
from .start_runtime import StartSummary, start_agents as _start_agents_impl
from .tmux_project_cleanup import ProjectTmuxCleanupSummary
from workspace.reconcile import format_workspace_blockers, reconcile_start_workspaces


def start_agents(context, command) -> StartSummary:
    return _start_agents_impl(
        context,
        command,
        ensure_daemon_started_fn=ensure_daemon_started,
        startup_report_store_cls=CcbdStartupReportStore,
        cleanup_summary_cls=ProjectTmuxCleanupSummary,
        before_client_start_fn=_reconcile_start_workspaces,
        enrich_summary_fn=_merge_workspace_guard_summary,
    )


def _reconcile_start_workspaces(context):
    summary = reconcile_start_workspaces(
        context.project.project_root,
        load_project_config(context.project.project_root).config,
    )
    if summary.blockers:
        raise RuntimeError(format_workspace_blockers('ccb start', summary.blockers))
    return summary


def _merge_workspace_guard_summary(context, summary: StartSummary, guard_summary) -> StartSummary:
    del context
    if guard_summary is None:
        return summary
    return replace(
        summary,
        worktree_warnings=tuple(getattr(guard_summary, 'warnings', ()) or ()),
        worktree_retired=tuple(getattr(guard_summary, 'retired', ()) or ()),
    )


__all__ = ['StartSummary', 'start_agents']
