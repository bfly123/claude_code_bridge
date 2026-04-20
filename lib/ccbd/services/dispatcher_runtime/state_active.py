from __future__ import annotations

from ccbd.api_models import TargetKind

from .state_common import TargetSlot


class DispatcherStateActiveMixin:
    def mark_active_for(self, target_kind: TargetKind | str, target_name: str, job_id: str) -> None:
        slot = self._normalize_slot(target_kind, target_name)
        self._ensure_queue(slot)
        self._active_jobs[slot] = job_id

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

    def active_job_for(self, target_kind: TargetKind | str, target_name: str) -> str | None:
        return self._active_jobs.get(self._normalize_slot(target_kind, target_name))

    def active_items(self) -> tuple[tuple[TargetKind, str, str], ...]:
        return tuple((slot[0], slot[1], job_id) for slot, job_id in self._active_jobs.items())

    def slots(self) -> tuple[TargetSlot, ...]:
        return tuple(self._queues.keys())


__all__ = ['DispatcherStateActiveMixin']
