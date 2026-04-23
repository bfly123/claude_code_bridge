from __future__ import annotations

from dataclasses import dataclass, replace
import os

from ccbd.socket_client import CcbdClient


@dataclass(frozen=True)
class StartSummary:
    project_root: str
    project_id: str
    started: tuple[str, ...]
    daemon_started: bool
    socket_path: str
    cleanup_summaries: tuple[object, ...] = ()
    worktree_warnings: tuple[object, ...] = ()
    worktree_retired: tuple[object, ...] = ()


_DEFAULT_START_REQUEST_TIMEOUT_S = 15.0


def start_agents(
    context,
    command,
    *,
    ensure_daemon_started_fn,
    startup_report_store_cls,
    cleanup_summary_cls,
    before_client_start_fn=None,
    enrich_summary_fn=None,
) -> StartSummary:
    pre_start_result = before_client_start_fn(context) if before_client_start_fn is not None else None
    handle = ensure_daemon_started_fn(context)
    assert handle.client is not None
    start_client = _start_request_client(handle.client)
    payload = start_client.start(
        agent_names=command.agent_names,
        restore=command.restore,
        auto_permission=command.auto_permission,
    )
    _record_daemon_started_flag(
        context,
        daemon_started=handle.started,
        startup_report_store_cls=startup_report_store_cls,
    )
    summary = _summary_from_start_payload(
        context,
        payload,
        daemon_started=handle.started,
        cleanup_summary_cls=cleanup_summary_cls,
    )
    if enrich_summary_fn is not None:
        return enrich_summary_fn(context, summary, pre_start_result)
    return summary


def _summary_from_start_payload(context, payload: dict, *, daemon_started: bool, cleanup_summary_cls) -> StartSummary:
    return StartSummary(
        project_root=str(payload.get("project_root") or context.project.project_root),
        project_id=str(payload.get("project_id") or context.project.project_id),
        started=_started_agents(payload),
        daemon_started=daemon_started,
        socket_path=str(payload.get("socket_path") or context.paths.ccbd_ipc_ref),
        cleanup_summaries=_cleanup_summaries(payload, cleanup_summary_cls=cleanup_summary_cls),
    )


def _started_agents(payload: dict) -> tuple[str, ...]:
    return tuple(
        str(item).strip()
        for item in (payload.get("started") or ())
        if str(item).strip()
    )


def _cleanup_summaries(payload: dict, *, cleanup_summary_cls) -> tuple[object, ...]:
    return tuple(
        cleanup_summary_cls(
            socket_name=item.get("socket_name"),
            owned_panes=tuple(item.get("owned_panes") or ()),
            active_panes=tuple(item.get("active_panes") or ()),
            orphaned_panes=tuple(item.get("orphaned_panes") or ()),
            killed_panes=tuple(item.get("killed_panes") or ()),
        )
        for item in (payload.get("cleanup_summaries") or ())
        if isinstance(item, dict)
    )


def _record_daemon_started_flag(context, *, daemon_started: bool, startup_report_store_cls) -> None:
    store = startup_report_store_cls(context.paths)
    try:
        report = store.load()
        if report is None:
            return
        store.save(replace(report, daemon_started=daemon_started))
    except Exception:
        return


def _start_request_timeout_s() -> float:
    raw = str(os.environ.get('CCB_CCBD_START_REQUEST_TIMEOUT_S') or '').strip()
    if raw:
        try:
            return max(1.0, float(raw))
        except Exception:
            pass
    return _DEFAULT_START_REQUEST_TIMEOUT_S


def _start_request_client(client):
    if not isinstance(client, CcbdClient):
        return client
    timeout_s = max(float(getattr(client, '_timeout_s', 0.0) or 0.0), _start_request_timeout_s())
    return CcbdClient(
        client._socket_path,
        timeout_s=timeout_s,
        ipc_kind=getattr(client, '_ipc_kind', None),
    )


__all__ = ["StartSummary", "start_agents"]
