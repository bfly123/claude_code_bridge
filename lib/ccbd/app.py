from __future__ import annotations

from pathlib import Path
import os
import uuid

from agents.config_identity import project_config_identity_payload
from agents.config_loader import load_project_config
from agents.store import AgentRestoreStore
from ccbd.lifecycle_report_store import CcbdShutdownReportStore, CcbdStartupReportStore
from ccbd.handlers import (
    build_ack_handler,
    build_attach_handler,
    build_cancel_handler,
    build_get_handler,
    build_inbox_handler,
    build_ping_handler,
    build_queue_handler,
    build_resubmit_handler,
    build_restore_handler,
    build_retry_handler,
    build_shutdown_handler,
    build_start_handler,
    build_stop_all_handler,
    build_submit_handler,
    build_trace_handler,
    build_watch_handler,
)
from ccbd.models import CcbdStartupReport
from ccbd.restore_report_store import CcbdRestoreReportStore
from ccbd.services.project_namespace import ProjectNamespaceController
from ccbd.services.project_namespace_state import ProjectNamespaceEventStore, ProjectNamespaceStateStore
from ccbd.services.start_policy import CcbdStartPolicy, CcbdStartPolicyStore, recovery_start_options
from ccbd.services import (
    AgentRegistry,
    HealthMonitor,
    JobDispatcher,
    JobHeartbeatService,
    MountManager,
    OwnershipGuard,
    RuntimeService,
    SnapshotWriter,
)
from ccbd.supervision import RuntimeSupervisionLoop
from ccbd.socket_server import CcbdSocketServer
from ccbd.supervisor import RuntimeSupervisor
from ccbd.system import utc_now
from completion.tracker import CompletionTrackerService
from fault_injection import FaultInjectionService
from heartbeat import HeartbeatPolicy, HeartbeatStateStore
from project.ids import compute_project_id
from provider_core.catalog import build_default_provider_catalog
from provider_execution.registry import build_default_execution_registry
from provider_execution.service import ExecutionService
from provider_execution.state_store import ExecutionStateStore
from storage.paths import PathLayout

_APP_REQUEST_TIMEOUT_S = 0.0
_JOB_HEARTBEAT_SILENCE_START_AFTER_S = 600.0
_JOB_HEARTBEAT_REPEAT_INTERVAL_S = 600.0


class CcbdApp:
    def __init__(self, project_root: str | Path, *, clock=utc_now, pid: int | None = None) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.project_id = compute_project_id(self.project_root)
        self.paths = PathLayout(self.project_root)
        self.clock = clock
        self.pid = pid or os.getpid()
        self.config = load_project_config(self.project_root).config
        self.config_identity = project_config_identity_payload(self.config)
        keeper_pid = str(os.environ.get('CCB_KEEPER_PID') or '').strip()
        self.keeper_pid = int(keeper_pid) if keeper_pid.isdigit() and int(keeper_pid) > 0 else None
        self.daemon_instance_id = uuid.uuid4().hex
        self.provider_catalog = build_default_provider_catalog()
        self.mount_manager = MountManager(self.paths, clock=self.clock)
        self.restore_report_store = CcbdRestoreReportStore(self.paths)
        self.startup_report_store = CcbdStartupReportStore(self.paths)
        self.shutdown_report_store = CcbdShutdownReportStore(self.paths)
        self.namespace_state_store = ProjectNamespaceStateStore(self.paths)
        self.namespace_event_store = ProjectNamespaceEventStore(self.paths)
        self.start_policy_store = CcbdStartPolicyStore(self.paths)
        self.ownership_guard = OwnershipGuard(self.paths, self.mount_manager, clock=self.clock)
        self.registry = AgentRegistry(self.paths, self.config)
        self.restore_store = AgentRestoreStore(self.paths)
        self.runtime_service = RuntimeService(self.paths, self.registry, self.project_id, self.restore_store, clock=self.clock)
        self.project_namespace = ProjectNamespaceController(self.paths, self.project_id, clock=self.clock)
        self.runtime_supervisor = RuntimeSupervisor(
            project_root=self.project_root,
            project_id=self.project_id,
            paths=self.paths,
            config=self.config,
            registry=self.registry,
            runtime_service=self.runtime_service,
            project_namespace=self.project_namespace,
            clock=self.clock,
        )
        self.runtime_supervision = RuntimeSupervisionLoop(
            project_id=self.project_id,
            layout=self.paths,
            config=self.config,
            registry=self.registry,
            runtime_service=self.runtime_service,
            mount_agent_fn=self._mount_agent_from_policy,
            remount_project_fn=self._remount_project_from_policy,
            clock=self.clock,
            generation_getter=lambda: self.lease.generation if self.lease is not None else None,
        )
        self.snapshot_writer = SnapshotWriter(self.paths, clock=self.clock)
        self.execution_registry = build_default_execution_registry()
        self.fault_injection = FaultInjectionService(self.paths, clock=self.clock)
        self.execution_service = ExecutionService(
            self.execution_registry,
            clock=self.clock,
            state_store=ExecutionStateStore(self.paths),
            fault_injection=self.fault_injection,
        )
        self.completion_tracker = CompletionTrackerService(
            self.config,
            self.provider_catalog,
            request_timeout_s=_APP_REQUEST_TIMEOUT_S,
        )
        self.dispatcher = JobDispatcher(
            self.paths,
            self.config,
            self.registry,
            runtime_service=self.runtime_service,
            execution_service=self.execution_service,
            auto_reply_delivery_on_complete=True,
            require_actionable_runtime_binding_for_execution=True,
            completion_tracker=self.completion_tracker,
            provider_catalog=self.provider_catalog,
            snapshot_writer=self.snapshot_writer,
            clock=self.clock,
        )
        self.heartbeat_state_store = HeartbeatStateStore(self.paths)
        self.job_heartbeat = JobHeartbeatService(
            self.paths,
            policy=HeartbeatPolicy(
                silence_start_after_s=_JOB_HEARTBEAT_SILENCE_START_AFTER_S,
                repeat_interval_s=_JOB_HEARTBEAT_REPEAT_INTERVAL_S,
            ),
            store=self.heartbeat_state_store,
            clock=self.clock,
        )
        self.health_monitor = HealthMonitor(
            self.registry,
            self.ownership_guard,
            clock=self.clock,
            namespace_state_store=self.namespace_state_store,
        )
        self.socket_server = CcbdSocketServer(self.paths.ccbd_socket_path)
        self.lease = None
        self._register_handlers()

    def _register_handlers(self) -> None:
        self.socket_server.register_handler('submit', build_submit_handler(self.dispatcher))
        self.socket_server.register_handler('get', build_get_handler(self.dispatcher, health_monitor=self.health_monitor))
        self.socket_server.register_handler('watch', build_watch_handler(self.dispatcher, health_monitor=self.health_monitor))
        self.socket_server.register_handler('queue', build_queue_handler(self.dispatcher))
        self.socket_server.register_handler('trace', build_trace_handler(self.dispatcher))
        self.socket_server.register_handler('resubmit', build_resubmit_handler(self.dispatcher))
        self.socket_server.register_handler('retry', build_retry_handler(self.dispatcher))
        self.socket_server.register_handler('inbox', build_inbox_handler(self.dispatcher))
        self.socket_server.register_handler('ack', build_ack_handler(self.dispatcher))
        self.socket_server.register_handler('cancel', build_cancel_handler(self.dispatcher))
        self.socket_server.register_handler(
            'ping',
            build_ping_handler(
                project_id=self.project_id,
                config=self.config,
                registry=self.registry,
                health_monitor=self.health_monitor,
                execution_state_store=self.execution_service._state_store,
                execution_registry=self.execution_registry,
                restore_report_store=self.restore_report_store,
                namespace_state_store=self.namespace_state_store,
                namespace_event_store=self.namespace_event_store,
                start_policy_store=self.start_policy_store,
            ),
        )
        self.socket_server.register_handler('attach', build_attach_handler(self.runtime_service))
        self.socket_server.register_handler('start', build_start_handler(self))
        self.socket_server.register_handler('restore', build_restore_handler(self.runtime_service))
        self.socket_server.register_handler('stop-all', build_stop_all_handler(self))
        self.socket_server.register_handler('shutdown', build_shutdown_handler(self))

    def start(self):
        with self.ownership_guard.startup_lock():
            generation = self.ownership_guard.verify_or_takeover(
                project_id=self.project_id,
                pid=self.pid,
                socket_path=self.paths.ccbd_socket_path,
            )
            self.lease = self.mount_manager.mark_mounted(
                project_id=self.project_id,
                pid=self.pid,
                socket_path=self.paths.ccbd_socket_path,
                generation=generation,
                config_signature=str(self.config_identity['config_signature']),
                keeper_pid=self.keeper_pid,
                daemon_instance_id=self.daemon_instance_id,
            )
            try:
                self.socket_server.listen()
            except Exception as exc:
                self.lease = self.mount_manager.mark_unmounted()
                self.socket_server.shutdown()
                self._record_startup_report(
                    trigger='daemon_boot',
                    status='failed',
                    actions_taken=('mount_backend', 'listen_socket_failed'),
                    failure_reason=str(exc),
                )
                raise
        try:
            self.dispatcher.restore_running_jobs()
            restore_report = self.dispatcher.last_restore_report(project_id=self.project_id)
            if restore_report is not None:
                self.restore_report_store.save(restore_report)
            self._record_startup_report(
                trigger='daemon_boot',
                status='ok',
                actions_taken=('mount_backend', 'listen_socket', 'restore_running_jobs'),
                restore_summary=restore_report.summary_fields() if restore_report is not None else {},
            )
        except Exception as exc:
            self.request_shutdown()
            self._record_startup_report(
                trigger='daemon_boot',
                status='failed',
                actions_taken=('mount_backend', 'listen_socket', 'restore_running_jobs_failed'),
                failure_reason=str(exc),
            )
            raise
        return self.lease

    def heartbeat(self):
        self.health_monitor.check_all()
        self.runtime_supervision.reconcile_once()
        self.dispatcher.reconcile_runtime_views()
        self.dispatcher.tick()
        self.dispatcher.poll_completions()
        self.job_heartbeat.tick(self.dispatcher)
        self.lease = self.mount_manager.refresh_heartbeat()
        return self.lease

    def serve_forever(self, *, poll_interval: float = 0.2) -> None:
        if self.lease is None:
            self.start()
        effective_poll_interval = _effective_poll_interval(poll_interval)
        try:
            self.socket_server.serve_forever(poll_interval=effective_poll_interval, on_tick=self.heartbeat)
        finally:
            self.lease = self.mount_manager.mark_unmounted()
            self.socket_server.shutdown()

    def request_shutdown(self) -> None:
        self.lease = self.mount_manager.mark_unmounted()
        self.socket_server.shutdown()

    def shutdown(self) -> None:
        try:
            self.runtime_supervisor.stop_all(force=True)
        except Exception:
            pass
        self.request_shutdown()

    def _record_startup_report(
        self,
        *,
        trigger: str,
        status: str,
        actions_taken: tuple[str, ...],
        restore_summary: dict[str, object] | None = None,
        failure_reason: str | None = None,
    ) -> None:
        try:
            inspection = self.ownership_guard.inspect()
            report = CcbdStartupReport(
                project_id=self.project_id,
                generated_at=self.clock(),
                trigger=trigger,
                status=status,
                requested_agents=(),
                desired_agents=tuple(sorted(self.config.agents)),
                restore_requested=False,
                auto_permission=False,
                daemon_generation=self.lease.generation if self.lease is not None else inspection.generation,
                daemon_started=True,
                config_signature=str(self.config_identity.get('config_signature') or '').strip() or None,
                inspection=inspection.to_record(),
                restore_summary=dict(restore_summary or {}),
                actions_taken=actions_taken,
                cleanup_summaries=(),
                agent_results=(),
                failure_reason=failure_reason,
            )
            self.startup_report_store.save(report)
        except Exception:
            return

    def persist_start_policy(self, *, auto_permission: bool, source: str = 'start_command') -> None:
        self.start_policy_store.save(
            CcbdStartPolicy(
                project_id=self.project_id,
                auto_permission=bool(auto_permission),
                recovery_restore=True,
                last_started_at=self.clock(),
                source=str(source or 'start_command'),
            )
        )

    def recovery_start_options(self) -> tuple[bool, bool]:
        try:
            policy = self.start_policy_store.load()
        except Exception:
            policy = None
        return recovery_start_options(policy)

    def _mount_agent_from_policy(self, agent_name: str) -> None:
        restore, auto_permission = self.recovery_start_options()
        self.runtime_supervisor.start(
            agent_names=(agent_name,),
            restore=restore,
            auto_permission=auto_permission,
            cleanup_tmux_orphans=False,
            interactive_tmux_layout=False,
        )

    def _remount_project_from_policy(self, reason: str) -> None:
        restore, auto_permission = self.recovery_start_options()
        self.runtime_supervisor.start(
            agent_names=tuple(self.config.agents),
            restore=restore,
            auto_permission=auto_permission,
            cleanup_tmux_orphans=False,
            interactive_tmux_layout=True,
            recreate_namespace=True,
            recreate_reason=reason,
        )


def _effective_poll_interval(poll_interval: float) -> float:
    try:
        requested = float(poll_interval)
    except Exception:
        requested = 0.2
    try:
        minimum = float(os.environ.get('CCB_CCBD_MIN_POLL_INTERVAL_S', '0'))
    except Exception:
        minimum = 0.0
    requested = max(0.0, requested)
    minimum = max(0.0, minimum)
    return max(requested, minimum)


__all__ = ['CcbdApp']
