from __future__ import annotations

from pathlib import Path

from ccbd.app_runtime import (
    execute_project_stop as execute_project_stop_impl,
    heartbeat as heartbeat_impl,
    initialize_app,
    mount_agent_from_policy as mount_agent_from_policy_impl,
    persist_start_policy as persist_start_policy_impl,
    record_shutdown_report as record_shutdown_report_impl,
    record_startup_report as record_startup_report_impl,
    release_backend_ownership as release_backend_ownership_impl,
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

    def release_backend_ownership(self):
        return release_backend_ownership_impl(self)

    def execute_project_stop(
        self,
        *,
        force: bool,
        trigger: str,
        reason: str,
        clear_start_policy: bool,
    ):
        return execute_project_stop_impl(
            self,
            force=force,
            trigger=trigger,
            reason=reason,
            clear_start_policy=clear_start_policy,
        )

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

    def _record_shutdown_report(
        self,
        *,
        trigger: str,
        status: str,
        forced: bool,
        reason: str,
        stopped_agents: tuple[str, ...],
        actions_taken: tuple[str, ...],
        cleanup_summaries,
        failure_reason: str | None,
    ) -> None:
        record_shutdown_report_impl(
            self,
            trigger=trigger,
            status=status,
            forced=forced,
            reason=reason,
            stopped_agents=stopped_agents,
            actions_taken=actions_taken,
            cleanup_summaries=cleanup_summaries,
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
