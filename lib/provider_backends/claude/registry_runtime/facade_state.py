from __future__ import annotations


class ClaudeRegistryStateMixin:
    @property
    def _lock(self):
        return self._runtime_state.lock

    @_lock.setter
    def _lock(self, value) -> None:
        self._runtime_state.lock = value

    @property
    def _stop(self):
        return self._runtime_state.stop

    @_stop.setter
    def _stop(self, value) -> None:
        self._runtime_state.stop = value

    @property
    def _sessions(self):
        return self._runtime_state.sessions

    @_sessions.setter
    def _sessions(self, value) -> None:
        self._runtime_state.sessions = value

    @property
    def _watchers(self):
        return self._runtime_state.watchers

    @_watchers.setter
    def _watchers(self, value) -> None:
        self._runtime_state.watchers = value

    @property
    def _pending_logs(self):
        return self._runtime_state.pending_logs

    @_pending_logs.setter
    def _pending_logs(self, value) -> None:
        self._runtime_state.pending_logs = value

    @property
    def _log_last_check(self):
        return self._runtime_state.log_last_check

    @_log_last_check.setter
    def _log_last_check(self, value) -> None:
        self._runtime_state.log_last_check = value

    @property
    def _monitor_thread(self):
        return self._runtime_state.monitor_thread

    @_monitor_thread.setter
    def _monitor_thread(self, value) -> None:
        self._runtime_state.monitor_thread = value

    @property
    def _root_watcher(self):
        return self._runtime_state.root_watcher

    @_root_watcher.setter
    def _root_watcher(self, value) -> None:
        self._runtime_state.root_watcher = value


__all__ = ['ClaudeRegistryStateMixin']
