from __future__ import annotations

from ccbd.api_models import JobRecord
from completion.models import CompletionDecision

from fault_injection import FaultInjectionService
from .base import ProviderRuntimeContext, ProviderSubmission
from .registry import ProviderExecutionRegistry
from .state_store import ExecutionStateStore
from .service_runtime import (
    ExecutionRestoreResult,
    ExecutionUpdate,
    acknowledge,
    acknowledge_item,
    persist_submission,
    poll_updates,
    restore_submission,
)


class ExecutionService:
    def __init__(
        self,
        registry: ProviderExecutionRegistry,
        *,
        clock,
        state_store: ExecutionStateStore | None = None,
        fault_injection: FaultInjectionService | None = None,
    ) -> None:
        self._registry = registry
        self._clock = clock
        self._state_store = state_store
        self._fault_injection = fault_injection
        self._active: dict[str, ProviderSubmission] = {}
        self._runtime_contexts: dict[str, ProviderRuntimeContext | None] = {}
        self._pending_replays: dict[str, tuple[tuple, CompletionDecision | None]] = {}

    def start(self, job: JobRecord, *, runtime_context: ProviderRuntimeContext | None = None) -> None:
        now = self._clock()
        if self._fault_injection is not None:
            injected = self._fault_injection.consume_for_job(job, now=now)
            if injected is not None:
                items, decision = self._fault_injection.build_terminal_replay(job, injected)
                self._runtime_contexts[job.job_id] = runtime_context
                self._pending_replays[job.job_id] = (items, decision)
                return
        adapter = self._registry.get(job.provider)
        if adapter is None:
            return
        submission = adapter.start(job, context=runtime_context, now=now)
        self._active[job.job_id] = submission
        self._runtime_contexts[job.job_id] = runtime_context
        self._persist(job.job_id)

    def cancel(self, job_id: str) -> None:
        self._active.pop(job_id, None)
        self._runtime_contexts.pop(job_id, None)
        self._pending_replays.pop(job_id, None)
        if self._state_store is not None:
            self._state_store.remove(job_id)

    def finish(self, job_id: str) -> None:
        self._active.pop(job_id, None)
        self._runtime_contexts.pop(job_id, None)
        self._pending_replays.pop(job_id, None)
        if self._state_store is not None:
            self._state_store.remove(job_id)

    def acknowledge(self, job_id: str) -> None:
        acknowledge(self, job_id)

    def acknowledge_item(self, job_id: str, *, event_seq: int | None) -> None:
        acknowledge_item(self, job_id, event_seq=event_seq)

    def restore(self, job: JobRecord, *, runtime_context: ProviderRuntimeContext | None = None) -> ExecutionRestoreResult:
        return restore_submission(self, job, runtime_context=runtime_context)

    def poll(self) -> tuple[ExecutionUpdate, ...]:
        return poll_updates(self)

    def _persist(
        self,
        job_id: str,
        *,
        pending_items: tuple = (),
        applied_event_seqs: tuple[int, ...] = (),
        pending_decision=None,
    ) -> None:
        persist_submission(
            self,
            job_id,
            pending_decision=pending_decision,
            pending_items=pending_items,
            applied_event_seqs=applied_event_seqs,
        )


__all__ = ["ExecutionRestoreResult", "ExecutionService", "ExecutionUpdate"]
