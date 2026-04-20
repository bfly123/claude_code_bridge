from __future__ import annotations

from dataclasses import dataclass

from agents.models import normalize_agent_name

from .common import JobStatus, TargetKind


@dataclass(frozen=True)
class AcceptedJobReceipt:
    job_id: str
    agent_name: str
    status: JobStatus
    accepted_at: str
    target_kind: TargetKind = TargetKind.AGENT
    target_name: str = ""
    provider_instance: str | None = None

    def __post_init__(self) -> None:
        if not self.job_id:
            raise ValueError("job_id cannot be empty")
        object.__setattr__(self, "target_kind", TargetKind(self.target_kind))
        if self.target_kind is TargetKind.AGENT:
            normalized_agent = normalize_agent_name(self.target_name or self.agent_name)
            object.__setattr__(self, "agent_name", normalized_agent)
            object.__setattr__(self, "target_name", normalized_agent)
            object.__setattr__(self, "provider_instance", None)
        else:
            target_name = str(self.target_name or "").strip().lower()
            if not target_name:
                raise ValueError("provider receipt target_name cannot be empty")
            object.__setattr__(self, "target_name", target_name)
            if str(self.agent_name or "").strip():
                object.__setattr__(self, "agent_name", normalize_agent_name(self.agent_name))
            normalized_instance = str(self.provider_instance or "").strip().lower() or None
            object.__setattr__(self, "provider_instance", normalized_instance)
        if self.status not in {JobStatus.ACCEPTED, JobStatus.QUEUED, JobStatus.RUNNING}:
            raise ValueError("accepted receipt status must be accepted, queued, or running")
        if not self.accepted_at:
            raise ValueError("accepted_at cannot be empty")

    def to_record(self) -> dict[str, str]:
        return {
            "job_id": self.job_id,
            "agent_name": self.agent_name,
            "target_kind": self.target_kind.value,
            "target_name": self.target_name,
            "provider_instance": self.provider_instance,
            "status": self.status.value,
            "accepted_at": self.accepted_at,
        }


@dataclass(frozen=True)
class SubmitReceipt:
    accepted_at: str
    jobs: tuple[AcceptedJobReceipt, ...]
    submission_id: str | None = None

    def __post_init__(self) -> None:
        if not self.accepted_at:
            raise ValueError("accepted_at cannot be empty")
        if not self.jobs:
            raise ValueError("jobs cannot be empty")
        if self.submission_id is None and len(self.jobs) != 1:
            raise ValueError("single submit receipt requires exactly one job")

    @property
    def is_broadcast(self) -> bool:
        return self.submission_id is not None

    def to_record(self) -> dict:
        if self.submission_id is None:
            job = self.jobs[0]
            return {
                "job_id": job.job_id,
                "agent_name": job.agent_name,
                "target_kind": job.target_kind.value,
                "target_name": job.target_name,
                "provider_instance": job.provider_instance,
                "status": job.status.value,
                "accepted_at": self.accepted_at,
            }
        return {
            "submission_id": self.submission_id,
            "accepted_at": self.accepted_at,
            "jobs": [job.to_record() for job in self.jobs],
        }


@dataclass(frozen=True)
class CancelReceipt:
    job_id: str
    agent_name: str
    status: JobStatus
    cancelled_at: str
    target_kind: TargetKind = TargetKind.AGENT
    target_name: str = ""
    provider_instance: str | None = None

    def __post_init__(self) -> None:
        if not self.job_id:
            raise ValueError("job_id cannot be empty")
        object.__setattr__(self, "target_kind", TargetKind(self.target_kind))
        if self.target_kind is TargetKind.AGENT:
            normalized_agent = normalize_agent_name(self.target_name or self.agent_name)
            object.__setattr__(self, "agent_name", normalized_agent)
            object.__setattr__(self, "target_name", normalized_agent)
            object.__setattr__(self, "provider_instance", None)
        else:
            target_name = str(self.target_name or "").strip().lower()
            if not target_name:
                raise ValueError("provider receipt target_name cannot be empty")
            object.__setattr__(self, "target_name", target_name)
            if str(self.agent_name or "").strip():
                object.__setattr__(self, "agent_name", normalize_agent_name(self.agent_name))
            normalized_instance = str(self.provider_instance or "").strip().lower() or None
            object.__setattr__(self, "provider_instance", normalized_instance)
        if self.status is not JobStatus.CANCELLED:
            raise ValueError("cancel receipt status must be cancelled")
        if not self.cancelled_at:
            raise ValueError("cancelled_at cannot be empty")

    def to_record(self) -> dict[str, str]:
        return {
            "job_id": self.job_id,
            "agent_name": self.agent_name,
            "target_kind": self.target_kind.value,
            "target_name": self.target_name,
            "provider_instance": self.provider_instance,
            "status": self.status.value,
            "cancelled_at": self.cancelled_at,
        }


__all__ = ["AcceptedJobReceipt", "CancelReceipt", "SubmitReceipt"]
