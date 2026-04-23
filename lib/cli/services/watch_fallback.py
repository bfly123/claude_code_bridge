from __future__ import annotations

from completion.snapshot_store import CompletionSnapshotStore
from jobs.store import JobEventStore, JobStore
from storage.paths import PathLayout

_TERMINAL_JOB_STATUSES = frozenset({'completed', 'cancelled', 'failed', 'incomplete'})


def load_persisted_terminal_watch_payload(context, target: str, *, cursor: int = 0) -> dict | None:
    job_id = str(target or '').strip()
    if not job_id.startswith('job_'):
        return None

    layout = _context_layout(context)
    snapshot = CompletionSnapshotStore(layout).load(job_id)
    if snapshot is None:
        return None
    latest_decision = getattr(snapshot, 'latest_decision', None)
    if latest_decision is None or not bool(getattr(latest_decision, 'terminal', False)):
        return None

    agent_name = str(getattr(snapshot, 'agent_name', '') or '').strip()
    if not agent_name:
        return None

    job = JobStore(layout).get_latest(agent_name, job_id)
    target_kind = getattr(getattr(job, 'target_kind', None), 'value', None) or 'agent'
    target_name = str(getattr(job, 'target_name', None) or agent_name).strip() or agent_name
    provider = getattr(job, 'provider', None)
    provider_instance = getattr(job, 'provider_instance', None)
    status = _resolved_terminal_status(job, latest_decision=latest_decision)
    if status not in _TERMINAL_JOB_STATUSES:
        return None

    next_cursor, filtered_events = _read_job_events(
        layout,
        target_kind=target_kind,
        target_name=target_name,
        job_id=job_id,
        cursor=cursor,
    )
    return {
        'job_id': job_id,
        'agent_name': agent_name,
        'target_kind': target_kind,
        'target_name': target_name,
        'provider': provider,
        'provider_instance': provider_instance,
        'cursor': next_cursor,
        'generation': None,
        'terminal': True,
        'status': status,
        'reply': str(getattr(latest_decision, 'reply', '') or ''),
        'events': filtered_events,
    }


def _context_layout(context) -> PathLayout:
    layout = getattr(context, 'paths', None)
    if isinstance(layout, PathLayout):
        return layout
    project = getattr(context, 'project', None)
    project_root = getattr(project, 'project_root', None)
    if project_root is None:
        raise ValueError('context project root is required for persisted watch fallback')
    return PathLayout(project_root)


def _resolved_terminal_status(job, *, latest_decision) -> str:
    job_status = str(getattr(getattr(job, 'status', None), 'value', '') or '').strip().lower()
    if job_status in _TERMINAL_JOB_STATUSES:
        return job_status
    return str(getattr(getattr(latest_decision, 'status', None), 'value', '') or '').strip().lower()


def _read_job_events(
    layout: PathLayout,
    *,
    target_kind: str,
    target_name: str,
    job_id: str,
    cursor: int,
) -> tuple[int, list[dict]]:
    try:
        next_cursor, events = JobEventStore(layout).read_since_target(target_kind, target_name, cursor)
    except Exception:
        return cursor, []
    return next_cursor, [event.to_record() for event in events if event.job_id == job_id]


__all__ = ['load_persisted_terminal_watch_payload']
