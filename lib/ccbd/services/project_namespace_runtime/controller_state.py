from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ProjectNamespaceControllerState:
    layout: object
    project_id: str
    clock: object
    backend_factory: object
    state_store: object
    event_store: object
    layout_version: int


class ProjectNamespaceControllerStateMixin:
    @property
    def _layout(self):
        return self._runtime_state.layout

    @property
    def _project_id(self):
        return self._runtime_state.project_id

    @property
    def _clock(self):
        return self._runtime_state.clock

    @property
    def _backend_factory(self):
        return self._runtime_state.backend_factory

    @property
    def _state_store(self):
        return self._runtime_state.state_store

    @property
    def _event_store(self):
        return self._runtime_state.event_store

    @property
    def _layout_version(self):
        return self._runtime_state.layout_version


__all__ = [
    'ProjectNamespaceControllerState',
    'ProjectNamespaceControllerStateMixin',
]
