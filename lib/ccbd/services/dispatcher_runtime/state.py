from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

from ccbd.api_models import JobRecord, JobStatus, TargetKind

if TYPE_CHECKING:
    from jobs.store import JobStore

from .state_active import DispatcherStateActiveMixin
from .state_agents import DispatcherStateAgentMixin
from .state_common import TargetQueue, TargetSlot, _PENDING_STATES
from .state_index import DispatcherStateIndexMixin
from .state_queue import DispatcherStateQueueMixin


class DispatcherState(
    DispatcherStateAgentMixin,
    DispatcherStateActiveMixin,
    DispatcherStateIndexMixin,
    DispatcherStateQueueMixin,
):
    def __init__(self, agent_names: Iterable[str]) -> None:
        self._queues: dict[TargetSlot, TargetQueue] = {}
        for name in agent_names:
            self._ensure_queue((TargetKind.AGENT, str(name)))
        self._job_index: dict[str, TargetSlot] = {}
        self._active_jobs: dict[TargetSlot, str] = {}

    def _ensure_queue(self, slot: TargetSlot) -> TargetQueue:
        queue = self._queues.get(slot)
        if queue is None:
            queue = TargetQueue()
            self._queues[slot] = queue
        return queue

    def _normalize_slot(self, target_kind: TargetKind | str, target_name: str) -> TargetSlot:
        return TargetKind(target_kind), str(target_name)

    def rebuild(self, job_store: JobStore, *, agent_names: Iterable[str]) -> None:
        self._job_index.clear()
        self._active_jobs.clear()
        for queue in self._queues.values():
            queue.clear()
        for agent_name in agent_names:
            latest_by_job: dict[str, JobRecord] = {}
            order: list[str] = []
            for record in job_store.list_agent(agent_name):
                if record.job_id not in latest_by_job:
                    order.append(record.job_id)
                latest_by_job[record.job_id] = record
                self._job_index[record.job_id] = self._normalize_slot(record.target_kind, record.target_name)
                self._ensure_queue((record.target_kind, record.target_name))
            for job_id in order:
                latest = latest_by_job[job_id]
                slot = self._normalize_slot(latest.target_kind, latest.target_name)
                if latest.status is JobStatus.RUNNING:
                    self._active_jobs[slot] = job_id
                elif latest.status in _PENDING_STATES:
                    self._ensure_queue(slot).push(job_id)
