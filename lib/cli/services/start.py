from __future__ import annotations

from ccbd.lifecycle_report_store import CcbdStartupReportStore

from .daemon import ensure_daemon_started
from .start_runtime import StartSummary, start_agents as _start_agents_impl
from .tmux_project_cleanup import ProjectTmuxCleanupSummary


def start_agents(context, command) -> StartSummary:
    return _start_agents_impl(
        context,
        command,
        ensure_daemon_started_fn=ensure_daemon_started,
        startup_report_store_cls=CcbdStartupReportStore,
        cleanup_summary_cls=ProjectTmuxCleanupSummary,
    )


__all__ = ['StartSummary', 'start_agents']
