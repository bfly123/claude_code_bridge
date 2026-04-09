from __future__ import annotations

from ccbd.api_models import JobRecord, JobStatus, TargetKind


def should_track_heartbeat_job(job: JobRecord | None, *, tracked_message_types) -> bool:
    if job is None or job.status is not JobStatus.RUNNING:
        return False
    if job.target_kind is not TargetKind.AGENT:
        return False
    message_type = str(job.request.message_type or '').strip().lower()
    return message_type in tracked_message_types


def tracked_running_jobs(service, dispatcher):
    for _target_kind, _target_name, job_id in dispatcher._state.active_items():
        job = dispatcher.get(job_id)
        if should_track_heartbeat_job(
            job,
            tracked_message_types=service._tracked_message_types,
        ):
            yield job


def cleanup_inactive_heartbeats(service, active_job_ids: set[str]) -> None:
    for state in service._store.list_all(subject_kind=service._subject_kind):
        if state.subject_id in active_job_ids:
            continue
        service._store.remove(state.subject_kind, state.subject_id)


__all__ = [
    'cleanup_inactive_heartbeats',
    'should_track_heartbeat_job',
    'tracked_running_jobs',
]
