from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable

from ccbd.api_models import JobRecord, JobStatus, TargetKind

if TYPE_CHECKING:
    from jobs.store import JobStore

_PENDING_STATES = frozenset({JobStatus.ACCEPTED, JobStatus.QUEUED})
TargetSlot = tuple[TargetKind, str]


@dataclass
class TargetQueue:
    items: list[str]

    def __init__(self) -> None:
        self.items = []

    def clear(self) -> None:
        self.items.clear()

    def push(self, job_id: str) -> None:
        self.items.append(job_id)

    def pop(self) -> str | None:
        if not self.items:
            return None
        return self.items.pop(0)

    def remove(self, job_id: str) -> bool:
        try:
            self.items.remove(job_id)
        except ValueError:
            return False
        return True

    def __len__(self) -> int:
        return len(self.items)


class DispatcherState:
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

    def target_for_job(self, job_id: str) -> TargetSlot | None:
        return self._job_index.get(job_id)

    def agent_for_job(self, job_id: str) -> str | None:
        slot = self.target_for_job(job_id)
        if slot is None or slot[0] is not TargetKind.AGENT:
            return None
        return slot[1]

    def remember_job(self, job_id: str, target_kind: TargetKind | str, target_name: str) -> None:
        slot = self._normalize_slot(target_kind, target_name)
        self._job_index[job_id] = slot
        self._ensure_queue(slot)

    def record(self, record: JobRecord) -> None:
        self.remember_job(record.job_id, record.target_kind, record.target_name)

    def queue_depth(self, agent_name: str) -> int:
        return self.queue_depth_for(TargetKind.AGENT, agent_name)

    def queue_depth_for(self, target_kind: TargetKind | str, target_name: str) -> int:
        slot = self._normalize_slot(target_kind, target_name)
        queue = self._ensure_queue(slot)
        return len(queue) + (1 if slot in self._active_jobs else 0)

    def has_outstanding(self, agent_name: str) -> bool:
        return self.has_outstanding_for(TargetKind.AGENT, agent_name)

    def has_outstanding_for(self, target_kind: TargetKind | str, target_name: str) -> bool:
        slot = self._normalize_slot(target_kind, target_name)
        queue = self._ensure_queue(slot)
        return self.active_job_for(target_kind, target_name) is not None or len(queue) > 0

    def enqueue(self, agent_name: str, job_id: str) -> None:
        self.enqueue_for(TargetKind.AGENT, agent_name, job_id)

    def enqueue_for(self, target_kind: TargetKind | str, target_name: str, job_id: str) -> None:
        self._ensure_queue(self._normalize_slot(target_kind, target_name)).push(job_id)

    def pop_next(self, agent_name: str) -> str | None:
        return self.pop_next_for(TargetKind.AGENT, agent_name)

    def pop_next_for(self, target_kind: TargetKind | str, target_name: str) -> str | None:
        return self._ensure_queue(self._normalize_slot(target_kind, target_name)).pop()

    def queued_items_for(self, target_kind: TargetKind | str, target_name: str) -> tuple[str, ...]:
        return tuple(self._ensure_queue(self._normalize_slot(target_kind, target_name)).items)

    def remove_queued(self, agent_name: str, job_id: str) -> bool:
        return self.remove_queued_for(TargetKind.AGENT, agent_name, job_id)

    def remove_queued_for(self, target_kind: TargetKind | str, target_name: str, job_id: str) -> bool:
        return self._ensure_queue(self._normalize_slot(target_kind, target_name)).remove(job_id)

    def mark_active(self, agent_name: str, job_id: str) -> None:
        self.mark_active_for(TargetKind.AGENT, agent_name, job_id)

    def mark_active_for(self, target_kind: TargetKind | str, target_name: str, job_id: str) -> None:
        slot = self._normalize_slot(target_kind, target_name)
        self._ensure_queue(slot)
        self._active_jobs[slot] = job_id

    def clear_active(self, agent_name: str, *, job_id: str | None = None) -> None:
        self.clear_active_for(TargetKind.AGENT, agent_name, job_id=job_id)

    def clear_active_for(
        self,
        target_kind: TargetKind | str,
        target_name: str,
        *,
        job_id: str | None = None,
    ) -> None:
        slot = self._normalize_slot(target_kind, target_name)
        if job_id is not None and self._active_jobs.get(slot) != job_id:
            return
        self._active_jobs.pop(slot, None)

    def active_job(self, agent_name: str) -> str | None:
        return self.active_job_for(TargetKind.AGENT, agent_name)

    def active_job_for(self, target_kind: TargetKind | str, target_name: str) -> str | None:
        return self._active_jobs.get(self._normalize_slot(target_kind, target_name))

    def active_items(self) -> tuple[tuple[TargetKind, str, str], ...]:
        return tuple((slot[0], slot[1], job_id) for slot, job_id in self._active_jobs.items())

    def slots(self) -> tuple[TargetSlot, ...]:
        return tuple(self._queues.keys())

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
