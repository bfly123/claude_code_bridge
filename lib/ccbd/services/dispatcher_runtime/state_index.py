from __future__ import annotations

from ccbd.api_models import JobRecord, TargetKind

from .state_common import TargetSlot


class DispatcherStateIndexMixin:
    def target_for_job(self, job_id: str) -> TargetSlot | None:
        return self._job_index.get(job_id)

    def remember_job(self, job_id: str, target_kind: TargetKind | str, target_name: str) -> None:
        slot = self._normalize_slot(target_kind, target_name)
        self._job_index[job_id] = slot
        self._ensure_queue(slot)

    def record(self, record: JobRecord) -> None:
        self.remember_job(record.job_id, record.target_kind, record.target_name)


__all__ = ['DispatcherStateIndexMixin']
