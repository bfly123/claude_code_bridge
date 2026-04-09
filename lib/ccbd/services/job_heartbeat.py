from __future__ import annotations

from ccbd.system import utc_now
from heartbeat import HeartbeatPolicy, HeartbeatStateStore
from storage.paths import PathLayout

from .job_heartbeat_runtime import (
    cleanup_inactive_heartbeats,
    should_track_heartbeat_job,
    tick_job_heartbeat,
    tracked_running_jobs,
)

_DEFAULT_SUBJECT_KIND = 'job_progress'
_TRACKED_MESSAGE_TYPES = frozenset({'ask'})


class JobHeartbeatService:
    def __init__(
        self,
        layout: PathLayout,
        *,
        policy: HeartbeatPolicy,
        store: HeartbeatStateStore | None = None,
        clock=utc_now,
        subject_kind: str = _DEFAULT_SUBJECT_KIND,
    ) -> None:
        self._layout = layout
        self._policy = policy
        self._store = store or HeartbeatStateStore(layout)
        self._clock = clock
        self._subject_kind = (
            str(subject_kind or _DEFAULT_SUBJECT_KIND).strip() or _DEFAULT_SUBJECT_KIND
        )
        self._tracked_message_types = _TRACKED_MESSAGE_TYPES

    def tick(self, dispatcher) -> tuple[str, ...]:
        active_job_ids: set[str] = set()
        for job in tracked_running_jobs(self, dispatcher):
            if tick_job_heartbeat(self, dispatcher, job):
                active_job_ids.add(job.job_id)
        cleanup_inactive_heartbeats(self, active_job_ids)
        return tuple(sorted(active_job_ids))

    def _should_track(self, job) -> bool:
        return should_track_heartbeat_job(
            job,
            tracked_message_types=self._tracked_message_types,
        )


__all__ = ['JobHeartbeatService']
