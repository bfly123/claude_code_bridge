from __future__ import annotations

from agents.config_loader import load_project_config
from agents.store import AgentRuntimeStore
from ccbd.lifecycle_report_store import CcbdShutdownReportStore
from ccbd.models import CcbdRuntimeSnapshot, CcbdShutdownReport, cleanup_summaries_from_objects
from ccbd.services.mount import MountManager
from ccbd.services.ownership import OwnershipGuard
from ccbd.system import utc_now

from ..daemon import KillSummary
from ..tmux_project_cleanup import ProjectTmuxCleanupSummary


def summary_from_stop_all_payload(payload: dict) -> KillSummary:
    cleanup_summaries = tuple(
        ProjectTmuxCleanupSummary(
            socket_name=item.get("socket_name"),
            owned_panes=tuple(item.get("owned_panes") or ()),
            active_panes=tuple(item.get("active_panes") or ()),
            orphaned_panes=tuple(item.get("orphaned_panes") or ()),
            killed_panes=tuple(item.get("killed_panes") or ()),
        )
        for item in (payload.get("cleanup_summaries") or ())
        if isinstance(item, dict)
    )
    return KillSummary(
        project_id=str(payload.get("project_id") or ""),
        state=str(payload.get("state") or "unmounted"),
        socket_path=str(payload.get("socket_path") or ""),
        forced=bool(payload.get("forced")),
        cleanup_summaries=cleanup_summaries,
    )


def merge_cleanup_summaries(*groups: tuple[ProjectTmuxCleanupSummary, ...]) -> tuple[ProjectTmuxCleanupSummary, ...]:
    merged: list[ProjectTmuxCleanupSummary] = []
    for group in groups:
        merged.extend(group)
    return tuple(merged)


def record_kill_report(
    context,
    *,
    trigger: str,
    forced: bool,
    cleanup_summaries: tuple[ProjectTmuxCleanupSummary, ...],
    extra_agent_dir_names_fn,
) -> None:
    store = CcbdShutdownReportStore(context.paths)
    runtime_store = AgentRuntimeStore(context.paths)
    manager = MountManager(context.paths)
    guard = OwnershipGuard(context.paths, manager)
    config = load_project_config(context.project.project_root).config
    snapshots = tuple(
        snapshot
        for snapshot in (
            snapshot_for_runtime(runtime_store.load_best_effort(agent_name))
            for agent_name in (*tuple(sorted(config.agents)), *extra_agent_dir_names_fn(context, tuple(config.agents)))
        )
        if snapshot is not None
    )
    try:
        inspection = guard.inspect()
    except Exception:
        return
    store.save(
        CcbdShutdownReport(
            project_id=context.project.project_id,
            generated_at=utc_now(),
            trigger=trigger,
            status="ok",
            forced=forced,
            stopped_agents=tuple(sorted(config.agents)),
            daemon_generation=inspection.generation,
            reason="kill",
            inspection_after=inspection.to_record(),
            actions_taken=(
                f"cleanup_tmux_orphans:killed={sum(len(item.killed_panes) for item in cleanup_summaries)}",
                "request_shutdown_intent",
            ),
            cleanup_summaries=cleanup_summaries_from_objects(cleanup_summaries),
            runtime_snapshots=snapshots,
            failure_reason=None,
        )
    )


def snapshot_for_runtime(runtime) -> CcbdRuntimeSnapshot | None:
    if runtime is None:
        return None
    try:
        return CcbdRuntimeSnapshot.from_runtime(runtime)
    except Exception:
        return None


__all__ = [
    "merge_cleanup_summaries",
    "record_kill_report",
    "snapshot_for_runtime",
    "summary_from_stop_all_payload",
]
