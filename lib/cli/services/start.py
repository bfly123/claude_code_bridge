from __future__ import annotations

from dataclasses import dataclass, replace

from ccbd.lifecycle_report_store import CcbdStartupReportStore

from cli.context import CliContext
from cli.models import ParsedStartCommand

from .daemon import ensure_daemon_started
from .tmux_project_cleanup import ProjectTmuxCleanupSummary


@dataclass(frozen=True)
class StartSummary:
    project_root: str
    project_id: str
    started: tuple[str, ...]
    daemon_started: bool
    socket_path: str
    cleanup_summaries: tuple[ProjectTmuxCleanupSummary, ...] = ()


def start_agents(context: CliContext, command: ParsedStartCommand) -> StartSummary:
    handle = ensure_daemon_started(context)
    assert handle.client is not None
    payload = handle.client.start(
        agent_names=command.agent_names,
        restore=command.restore,
        auto_permission=command.auto_permission,
    )
    _record_daemon_started_flag(context, daemon_started=handle.started)
    return _summary_from_start_payload(
        context,
        payload,
        daemon_started=handle.started,
    )


def _summary_from_start_payload(context: CliContext, payload: dict, *, daemon_started: bool) -> StartSummary:
    cleanup_summaries = tuple(
        ProjectTmuxCleanupSummary(
            socket_name=item.get('socket_name'),
            owned_panes=tuple(item.get('owned_panes') or ()),
            active_panes=tuple(item.get('active_panes') or ()),
            orphaned_panes=tuple(item.get('orphaned_panes') or ()),
            killed_panes=tuple(item.get('killed_panes') or ()),
        )
        for item in (payload.get('cleanup_summaries') or ())
        if isinstance(item, dict)
    )
    started = tuple(
        str(item).strip()
        for item in (payload.get('started') or ())
        if str(item).strip()
    )
    return StartSummary(
        project_root=str(payload.get('project_root') or context.project.project_root),
        project_id=str(payload.get('project_id') or context.project.project_id),
        started=started,
        daemon_started=daemon_started,
        socket_path=str(payload.get('socket_path') or context.paths.ccbd_socket_path),
        cleanup_summaries=cleanup_summaries,
    )


def _record_daemon_started_flag(context: CliContext, *, daemon_started: bool) -> None:
    store = CcbdStartupReportStore(context.paths)
    try:
        report = store.load()
        if report is None:
            return
        store.save(replace(report, daemon_started=daemon_started))
    except Exception:
        return


__all__ = ['StartSummary', 'start_agents']
