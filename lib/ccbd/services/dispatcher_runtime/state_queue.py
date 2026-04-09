from __future__ import annotations

from ccbd.api_models import TargetKind


class DispatcherStateQueueMixin:
    def queue_depth_for(self, target_kind: TargetKind | str, target_name: str) -> int:
        slot = self._normalize_slot(target_kind, target_name)
        queue = self._ensure_queue(slot)
        return len(queue) + (1 if slot in self._active_jobs else 0)

    def has_outstanding_for(self, target_kind: TargetKind | str, target_name: str) -> bool:
        slot = self._normalize_slot(target_kind, target_name)
        queue = self._ensure_queue(slot)
        return self.active_job_for(target_kind, target_name) is not None or len(queue) > 0

    def enqueue_for(self, target_kind: TargetKind | str, target_name: str, job_id: str) -> None:
        self._ensure_queue(self._normalize_slot(target_kind, target_name)).push(job_id)

    def pop_next_for(self, target_kind: TargetKind | str, target_name: str) -> str | None:
        return self._ensure_queue(self._normalize_slot(target_kind, target_name)).pop()

    def queued_items_for(self, target_kind: TargetKind | str, target_name: str) -> tuple[str, ...]:
        return tuple(self._ensure_queue(self._normalize_slot(target_kind, target_name)).items)

    def remove_queued_for(self, target_kind: TargetKind | str, target_name: str, job_id: str) -> bool:
        return self._ensure_queue(self._normalize_slot(target_kind, target_name)).remove(job_id)


__all__ = ['DispatcherStateQueueMixin']
