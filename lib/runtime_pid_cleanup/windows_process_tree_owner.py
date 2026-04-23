from __future__ import annotations

import os

from .process_tree_owner import ProcessTreeOwner, ProcessTreeTarget
from .windows_job_objects import terminate_named_job


class WindowsJobObjectProcessTreeOwner:
    def __init__(
        self,
        job_id: str,
        fallback_owner: ProcessTreeOwner,
        *,
        terminate_named_job_fn=None,
    ) -> None:
        self._job_id = str(job_id or '').strip()
        self._fallback_owner = fallback_owner
        self._terminate_named_job_fn = terminate_named_job_fn or terminate_named_job

    def terminate(self, pid: int, *, timeout_s: float, is_pid_alive_fn) -> bool:
        if self._job_id and self._terminate_named_job_fn(self._job_id):
            return True
        return self._fallback_owner.terminate(pid, timeout_s=timeout_s, is_pid_alive_fn=is_pid_alive_fn)


class WindowsJobMetadataProcessTreeOwnerFactory:
    def __init__(self, owner: ProcessTreeOwner, *, is_windows_fn=None, terminate_named_job_fn=None) -> None:
        self._owner = owner
        self._is_windows_fn = is_windows_fn or (lambda: os.name == 'nt')
        self._terminate_named_job_fn = terminate_named_job_fn or terminate_named_job

    def build(self, target: ProcessTreeTarget) -> ProcessTreeOwner | None:
        if not self._is_windows_fn():
            return None
        metadata = target.metadata or {}
        job_id = str(metadata.get('job_id') or '').strip()
        if job_id == '':
            return None
        owner_pid = _coerce_pid(metadata.get('job_owner_pid'))
        if owner_pid != target.pid:
            return None
        return WindowsJobObjectProcessTreeOwner(
            job_id,
            self._owner,
            terminate_named_job_fn=self._terminate_named_job_fn,
        )


def _coerce_pid(value: object) -> int | None:
    text = str(value or '').strip()
    if not text.isdigit():
        return None
    pid = int(text)
    return pid if pid > 0 else None


__all__ = ['WindowsJobMetadataProcessTreeOwnerFactory', 'WindowsJobObjectProcessTreeOwner']
