from __future__ import annotations

from pathlib import Path

from ccbd.app_runtime import (
    heartbeat as heartbeat_impl,
    initialize_app,
    mount_agent_from_policy as mount_agent_from_policy_impl,
    persist_start_policy as persist_start_policy_impl,
    record_startup_report as record_startup_report_impl,
    recovery_start_options as recovery_start_options_impl,
    request_shutdown as request_shutdown_impl,
    remount_project_from_policy as remount_project_from_policy_impl,
    serve_forever as serve_forever_impl,
    shutdown as shutdown_impl,
    start as start_impl,
)
from ccbd.system import utc_now


class CcbdApp:
    def __init__(self, project_root: str | Path, *, clock=utc_now, pid: int | None = None) -> None:
        initialize_app(self, project_root, clock=clock, pid=pid)

    def _register_handlers(self) -> None:
        from ccbd.app_runtime.handlers import register_handlers

        register_handlers(self)

    def start(self):
        return start_impl(self)

    def heartbeat(self):
        return heartbeat_impl(self)

    def serve_forever(self, *, poll_interval: float = 0.2) -> None:
        serve_forever_impl(self, poll_interval=poll_interval)

    def request_shutdown(self) -> None:
        request_shutdown_impl(self)

    def shutdown(self) -> None:
        shutdown_impl(self)

    def _record_startup_report(
        self,
        *,
        trigger: str,
        status: str,
        actions_taken: tuple[str, ...],
        restore_summary: dict[str, object] | None = None,
        failure_reason: str | None = None,
    ) -> None:
        record_startup_report_impl(
            self,
            trigger=trigger,
            status=status,
            actions_taken=actions_taken,
            restore_summary=restore_summary,
            failure_reason=failure_reason,
        )

    def persist_start_policy(self, *, auto_permission: bool, source: str = 'start_command') -> None:
        persist_start_policy_impl(self, auto_permission=auto_permission, source=source)

    def recovery_start_options(self) -> tuple[bool, bool]:
        return recovery_start_options_impl(self)

    def _mount_agent_from_policy(self, agent_name: str) -> None:
        mount_agent_from_policy_impl(self, agent_name)

    def _remount_project_from_policy(self, reason: str) -> None:
        remount_project_from_policy_impl(self, reason)


__all__ = ['CcbdApp']
