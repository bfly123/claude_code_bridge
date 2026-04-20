from __future__ import annotations

from pathlib import Path

from provider_backends.claude.registry_support.logs import (
    env_float as _env_float,
    env_int as _env_int,
    refresh_claude_log_binding as _refresh_claude_log_binding,
)

from . import (
    check_all_sessions as _check_all_sessions_impl,
    check_one as _check_one_impl,
    monitor_loop as _monitor_loop_impl,
    start_monitor as _start_monitor_impl,
    stop_monitor as _stop_monitor_impl,
)
from .facade_status import registry_status
from .logging import write_registry_log


class ClaudeRegistryMonitoringMixin:
    def start_monitor(self) -> None:
        _start_monitor_impl(self)

    def stop_monitor(self) -> None:
        _stop_monitor_impl(self)

    def _monitor_loop(self) -> None:
        _monitor_loop_impl(self)

    def _check_all_sessions(self) -> None:
        _check_all_sessions_impl(self, env_float_fn=_env_float, env_int_fn=_env_int)

    def _check_one(
        self,
        key: str,
        work_dir: Path,
        *,
        now: float,
        refresh_interval_s: float,
        scan_limit: int,
    ) -> None:
        _check_one_impl(
            self,
            key,
            work_dir,
            now=now,
            refresh_interval_s=refresh_interval_s,
            scan_limit=scan_limit,
            find_session_file_fn=self._find_claude_session_file,
            load_session_fn=self._load_claude_session,
            refresh_claude_log_binding_fn=_refresh_claude_log_binding,
            write_log_fn=write_registry_log,
        )

    def get_status(self) -> dict:
        return registry_status(self)


__all__ = ['ClaudeRegistryMonitoringMixin']
