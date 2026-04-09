from __future__ import annotations

from uuid import uuid4

from agents.models import AgentState
from completion.tracker import CompletionTrackerView

from .completion import apply_tracker_view, merge_terminal_decision
from .lifecycle import resubmit_message, retry_attempt
from .records import append_event, append_job, rebuild_dispatcher_state
from .routing import build_watch_payload, resolve_targets, resolve_watch_target, validate_sender, validate_targets_available
from .runtime_state import sync_runtime


class DispatcherFacadeMixin:
    def watch(self, target: str, *, start_line: int = 0) -> dict:
        return build_watch_payload(self, target, start_line=start_line)

    def queue(self, target: str = 'all') -> dict:
        payload = self._message_bureau_control.queue_summary(target)
        if payload.get('target') == 'all':
            payload = dict(payload)
            payload['agents'] = [self._queue_agent_with_runtime(agent) for agent in payload.get('agents') or ()]
            return payload
        payload = dict(payload)
        agent = payload.get('agent')
        if isinstance(agent, dict):
            payload['agent'] = self._queue_agent_with_runtime(agent)
        return payload

    def trace(self, target: str) -> dict:
        return self._message_bureau_control.trace(target)

    def resubmit(self, message_id: str) -> dict:
        return resubmit_message(self, message_id)

    def retry(self, target: str) -> dict:
        return retry_attempt(self, target)

    def inbox(self, agent_name: str) -> dict:
        return self._message_bureau_control.inbox(agent_name)

    def ack_reply(self, agent_name: str, inbound_event_id: str | None = None) -> dict:
        return self._message_bureau_control.ack_reply(agent_name, inbound_event_id)

    def _resolve_targets(self, request) -> tuple[str, ...]:
        return resolve_targets(self, request)

    def _validate_targets_available(self, targets) -> None:
        validate_targets_available(self, targets)

    def _validate_sender(self, sender: str) -> None:
        validate_sender(self, sender)

    def _resolve_watch_target(self, target: str) -> tuple[str, str]:
        return resolve_watch_target(self, target)

    def _profile_family(self, agent_name: str):
        spec = self._registry.spec_for(agent_name)
        manifest = self._provider_catalog.resolve_completion_manifest(spec.provider, spec.runtime_mode)
        return manifest.completion_family

    def _profile_family_for_job(self, job):
        return self._profile_family(job.agent_name)

    def _has_outstanding_work(self, agent_name: str) -> bool:
        return self._state.has_outstanding(agent_name)

    def _sync_runtime(self, agent_name: str, *, state: AgentState | None = None) -> None:
        sync_runtime(self, agent_name, state=state)

    def reconcile_runtime_views(self) -> None:
        for agent_name in self._config.agents:
            self._sync_runtime(agent_name)

    def _append_job(self, record) -> None:
        append_job(self, record)

    def _append_event(self, record, event_type: str, payload: dict[str, object], *, timestamp: str) -> None:
        append_event(self, record, event_type, payload, timestamp=timestamp)

    def _new_id(self, prefix: str) -> str:
        return f'{prefix}_{uuid4().hex[:12]}'

    def _rebuild_state(self) -> None:
        rebuild_dispatcher_state(self)

    def _apply_tracker_view(
        self,
        current,
        tracked: CompletionTrackerView,
        *,
        updated_at: str | None = None,
    ) -> bool:
        timestamp = apply_tracker_view(
            current,
            tracked,
            snapshot_writer=self._snapshot_writer,
            profile_family=self._profile_family_for_job(current),
            clock=self._clock,
            updated_at=updated_at,
        )
        if timestamp is None:
            return False
        self._append_event(current, 'completion_state_updated', tracked.state.to_record(), timestamp=timestamp)
        return True

    def _merge_terminal_decision(self, job_id: str, decision, *, prior_snapshot):
        return merge_terminal_decision(
            job_id,
            decision,
            completion_tracker=self._completion_tracker,
            prior_snapshot=prior_snapshot,
        )

    def _queue_agent_with_runtime(self, payload: dict) -> dict:
        agent = dict(payload)
        runtime = self._registry.get(agent.get('agent_name', ''))
        agent['runtime_state'] = runtime.state.value if runtime is not None else 'stopped'
        agent['runtime_health'] = runtime.health if runtime is not None else 'stopped'
        return agent


__all__ = ['DispatcherFacadeMixin']
