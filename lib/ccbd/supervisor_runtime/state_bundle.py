from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SupervisorRuntimeState:
    project_root: object
    project_id: str
    paths: object
    config: object
    config_identity: dict
    registry: object
    runtime_service: object
    project_namespace: object
    clock: object
    mount_manager: object
    ownership_guard: object
    startup_report_store: object
    shutdown_report_store: object
    start_policy_store: object


class SupervisorRuntimeStateMixin:
    @property
    def _project_root(self):
        return self._runtime_state.project_root

    @property
    def _project_id(self):
        return self._runtime_state.project_id

    @property
    def _paths(self):
        return self._runtime_state.paths

    @property
    def _config(self):
        return self._runtime_state.config

    @property
    def _config_identity(self):
        return self._runtime_state.config_identity

    @property
    def _registry(self):
        return self._runtime_state.registry

    @property
    def _runtime_service(self):
        return self._runtime_state.runtime_service

    @property
    def _project_namespace(self):
        return self._runtime_state.project_namespace

    @_project_namespace.setter
    def _project_namespace(self, value) -> None:
        self._runtime_state.project_namespace = value

    @property
    def _clock(self):
        return self._runtime_state.clock

    @property
    def _mount_manager(self):
        return self._runtime_state.mount_manager

    @property
    def _ownership_guard(self):
        return self._runtime_state.ownership_guard

    @property
    def _startup_report_store(self):
        return self._runtime_state.startup_report_store

    @property
    def _shutdown_report_store(self):
        return self._runtime_state.shutdown_report_store

    @property
    def _start_policy_store(self):
        return self._runtime_state.start_policy_store


__all__ = [
    'SupervisorRuntimeState',
    'SupervisorRuntimeStateMixin',
]
