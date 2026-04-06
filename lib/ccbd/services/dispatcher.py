from __future__ import annotations

from uuid import uuid4

from .dispatcher_runtime import (
    DispatcherState,
    apply_tracker_view,
    append_event,
    append_job,
    build_last_restore_report,
    build_watch_payload,
    cancel_job,
    cancel_with_decision,
    complete_job,
    get_job,
    latest_for_agent,
    merge_terminal_decision,
    poll_completion_updates,
    prepare_reply_deliveries,
    rebuild_dispatcher_state,
    resolve_targets,
    resolve_watch_target,
    restore_running_jobs,
    resubmit_message,
    retry_attempt,
    submit_jobs,
    sync_runtime,
    tick_jobs,
    validate_sender,
    validate_targets_available,
)
from agents.models import AgentState
from ccbd.api_models import (
    CancelReceipt,
    JobRecord,
    JobStatus,
    MessageEnvelope,
    SubmitReceipt,
)
from ccbd.models import CcbdRestoreEntry, CcbdRestoreReport
from ccbd.system import utc_now
from completion.models import CompletionDecision, CompletionFamily
from completion.tracker import CompletionTrackerService, CompletionTrackerView
from jobs.store import JobEventStore, JobStore, SubmissionStore
from mailbox_runtime.targets import COMMAND_MAILBOX_ACTOR
from message_bureau import MessageBureauControlService, MessageBureauFacade
from provider_core.catalog import ProviderCatalog, build_default_provider_catalog
from storage.paths import PathLayout

from .registry import AgentRegistry
from .snapshot_writer import SnapshotWriter

_TERMINAL_EVENT_BY_STATUS = {
    JobStatus.COMPLETED: 'job_completed',
    JobStatus.CANCELLED: 'job_cancelled',
    JobStatus.FAILED: 'job_failed',
    JobStatus.INCOMPLETE: 'job_incomplete',
}


class DispatchError(RuntimeError):
    pass


class DispatchRejectedError(DispatchError):
    pass


class JobDispatcher:
    def __init__(
        self,
        layout: PathLayout,
        config,
        registry: AgentRegistry,
        *,
        runtime_service=None,
        execution_service=None,
        auto_reply_delivery_on_complete: bool = False,
        require_actionable_runtime_binding_for_execution: bool = False,
        completion_tracker: CompletionTrackerService | None = None,
        provider_catalog: ProviderCatalog | None = None,
        job_store: JobStore | None = None,
        event_store: JobEventStore | None = None,
        submission_store: SubmissionStore | None = None,
        message_bureau: MessageBureauFacade | None = None,
        message_bureau_control: MessageBureauControlService | None = None,
        snapshot_writer: SnapshotWriter | None = None,
        clock=utc_now,
    ) -> None:
        self._layout = layout
        self._config = config
        self._registry = registry
        self._runtime_service = runtime_service
        self._execution_service = execution_service
        self._auto_reply_delivery_on_complete = bool(auto_reply_delivery_on_complete)
        self._require_actionable_runtime_binding_for_execution = bool(
            require_actionable_runtime_binding_for_execution
        )
        self._provider_catalog = provider_catalog or build_default_provider_catalog()
        self._completion_tracker = completion_tracker
        self._job_store = job_store or JobStore(layout)
        self._event_store = event_store or JobEventStore(layout)
        self._submission_store = submission_store or SubmissionStore(layout)
        self._message_bureau = message_bureau or MessageBureauFacade(layout, config=config, clock=clock)
        self._message_bureau_control = message_bureau_control or MessageBureauControlService(layout, config, clock=clock)
        self._snapshot_writer = snapshot_writer or SnapshotWriter(layout)
        self._clock = clock
        self._state = DispatcherState(config.agents)
        self._dispatch_error = DispatchError
        self._dispatch_rejected_error = DispatchRejectedError
        self._terminal_event_by_status = _TERMINAL_EVENT_BY_STATUS
        self._running_status = JobStatus.RUNNING
        self._last_restore_entries: tuple[CcbdRestoreEntry, ...] = ()
        self._last_restore_generated_at: str | None = None
        self._rebuild_state()

    def submit(self, request: MessageEnvelope) -> SubmitReceipt:
        return submit_jobs(self, request)

    def tick(self) -> tuple[JobRecord, ...]:
        prepare_reply_deliveries(self)
        return tick_jobs(self)

    def complete(self, job_id: str, decision: CompletionDecision) -> JobRecord:
        return complete_job(self, job_id, decision)

    def cancel(self, job_id: str) -> CancelReceipt:
        return cancel_job(self, job_id)

    def _cancel_with_decision(self, current: JobRecord, cancelled_at: str, reply: str, snapshot) -> CancelReceipt:
        return cancel_with_decision(self, current, cancelled_at, reply, snapshot)

    def get(self, job_id: str) -> JobRecord | None:
        return get_job(self, job_id)

    def get_snapshot(self, job_id: str):
        return self._snapshot_writer.load(job_id)

    def latest_for_agent(self, agent_name: str) -> JobRecord | None:
        return latest_for_agent(self, agent_name)

    def poll_completions(self) -> tuple[JobRecord, ...]:
        return poll_completion_updates(self)

    def restore_running_jobs(self) -> tuple[JobRecord, ...]:
        return restore_running_jobs(self)

    def last_restore_report(self, *, project_id: str) -> CcbdRestoreReport:
        return build_last_restore_report(self, project_id=project_id)

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

    def _resolve_targets(self, request: MessageEnvelope) -> tuple[str, ...]:
        return resolve_targets(self, request)

    def _validate_targets_available(self, targets) -> None:
        validate_targets_available(self, targets)

    def _validate_sender(self, sender: str) -> None:
        validate_sender(self, sender)

    def _resolve_watch_target(self, target: str) -> tuple[str, str]:
        return resolve_watch_target(self, target)

    def _profile_family(self, agent_name: str) -> CompletionFamily:
        spec = self._registry.spec_for(agent_name)
        manifest = self._provider_catalog.resolve_completion_manifest(spec.provider, spec.runtime_mode)
        return manifest.completion_family

    def _profile_family_for_job(self, job: JobRecord) -> CompletionFamily:
        return self._profile_family(job.agent_name)

    def _has_outstanding_work(self, agent_name: str) -> bool:
        return self._state.has_outstanding(agent_name)

    def _sync_runtime(self, agent_name: str, *, state: AgentState | None = None) -> None:
        sync_runtime(self, agent_name, state=state)

    def reconcile_runtime_views(self) -> None:
        for agent_name in self._config.agents:
            self._sync_runtime(agent_name)

    def _append_job(self, record: JobRecord) -> None:
        append_job(self, record)

    def _append_event(self, record: JobRecord, event_type: str, payload: dict[str, object], *, timestamp: str) -> None:
        append_event(self, record, event_type, payload, timestamp=timestamp)

    def _new_id(self, prefix: str) -> str:
        return f'{prefix}_{uuid4().hex[:12]}'

    def _rebuild_state(self) -> None:
        rebuild_dispatcher_state(self)

    def _apply_tracker_view(
        self,
        current: JobRecord,
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

    def _merge_terminal_decision(self, job_id: str, decision: CompletionDecision, *, prior_snapshot) -> CompletionDecision:
        return merge_terminal_decision(
            job_id,
            decision,
            completion_tracker=self._completion_tracker,
            prior_snapshot=prior_snapshot,
        )

    def _queue_agent_with_runtime(self, payload: dict) -> dict:
        agent = dict(payload)
        if agent.get('agent_name') == COMMAND_MAILBOX_ACTOR:
            agent['runtime_state'] = 'mailbox'
            agent['runtime_health'] = 'mailbox'
            return agent
        runtime = self._registry.get(agent.get('agent_name', ''))
        agent['runtime_state'] = runtime.state.value if runtime is not None else 'stopped'
        agent['runtime_health'] = runtime.health if runtime is not None else 'stopped'
        return agent


__all__ = ['JobDispatcher']
