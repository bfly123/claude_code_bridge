from __future__ import annotations

from dataclasses import dataclass


@dataclass
class KeeperAppState:
    project_root: object
    paths: object
    clock: object
    pid: int
    sleep: object
    spawn_ccbd_process: object
    process_exists: object
    mount_manager: object
    lifecycle_store: object
    ownership_guard: object
    state_store: object
    intent_store: object


class KeeperAppStateMixin:
    @property
    def project_root(self):
        return self._runtime_state.project_root

    @property
    def paths(self):
        return self._runtime_state.paths

    @property
    def clock(self):
        return self._runtime_state.clock

    @property
    def pid(self):
        return self._runtime_state.pid

    @property
    def _sleep(self):
        return self._runtime_state.sleep

    @property
    def _spawn_ccbd_process(self):
        return self._runtime_state.spawn_ccbd_process

    @property
    def _process_exists(self):
        return self._runtime_state.process_exists

    @property
    def _mount_manager(self):
        return self._runtime_state.mount_manager

    @property
    def _lifecycle_store(self):
        return self._runtime_state.lifecycle_store

    @property
    def _ownership_guard(self):
        return self._runtime_state.ownership_guard

    @_ownership_guard.setter
    def _ownership_guard(self, value) -> None:
        self._runtime_state.ownership_guard = value

    @property
    def _state_store(self):
        return self._runtime_state.state_store

    @property
    def _intent_store(self):
        return self._runtime_state.intent_store


__all__ = [
    'KeeperAppState',
    'KeeperAppStateMixin',
]
