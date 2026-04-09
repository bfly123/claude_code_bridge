from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ExecutionServiceRuntimeState:
    registry: object
    clock: object
    state_store: object
    fault_injection: object
    active: dict
    runtime_contexts: dict
    pending_replays: dict


class ExecutionServiceStateMixin:
    @property
    def _registry(self):
        return self._runtime_state.registry

    @property
    def _clock(self):
        return self._runtime_state.clock

    @property
    def _state_store(self):
        return self._runtime_state.state_store

    @property
    def _fault_injection(self):
        return self._runtime_state.fault_injection

    @property
    def _active(self):
        return self._runtime_state.active

    @_active.setter
    def _active(self, value) -> None:
        self._runtime_state.active = value

    @property
    def _runtime_contexts(self):
        return self._runtime_state.runtime_contexts

    @_runtime_contexts.setter
    def _runtime_contexts(self, value) -> None:
        self._runtime_state.runtime_contexts = value

    @property
    def _pending_replays(self):
        return self._runtime_state.pending_replays

    @_pending_replays.setter
    def _pending_replays(self, value) -> None:
        self._runtime_state.pending_replays = value


__all__ = [
    'ExecutionServiceRuntimeState',
    'ExecutionServiceStateMixin',
]
