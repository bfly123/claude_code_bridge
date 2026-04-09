from __future__ import annotations

from ccbd.api_models import TargetKind


class DispatcherStateAgentMixin:
    def agent_for_job(self, job_id: str) -> str | None:
        slot = self.target_for_job(job_id)
        if slot is None or slot[0] is not TargetKind.AGENT:
            return None
        return slot[1]

    def queue_depth(self, agent_name: str) -> int:
        return self.queue_depth_for(TargetKind.AGENT, agent_name)

    def has_outstanding(self, agent_name: str) -> bool:
        return self.has_outstanding_for(TargetKind.AGENT, agent_name)

    def enqueue(self, agent_name: str, job_id: str) -> None:
        self.enqueue_for(TargetKind.AGENT, agent_name, job_id)

    def pop_next(self, agent_name: str) -> str | None:
        return self.pop_next_for(TargetKind.AGENT, agent_name)

    def remove_queued(self, agent_name: str, job_id: str) -> bool:
        return self.remove_queued_for(TargetKind.AGENT, agent_name, job_id)

    def mark_active(self, agent_name: str, job_id: str) -> None:
        self.mark_active_for(TargetKind.AGENT, agent_name, job_id)

    def clear_active(self, agent_name: str, *, job_id: str | None = None) -> None:
        self.clear_active_for(TargetKind.AGENT, agent_name, job_id=job_id)

    def active_job(self, agent_name: str) -> str | None:
        return self.active_job_for(TargetKind.AGENT, agent_name)


__all__ = ['DispatcherStateAgentMixin']
