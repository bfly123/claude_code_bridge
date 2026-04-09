from __future__ import annotations

from pathlib import Path
import os
import uuid

from agents.config_identity import project_config_identity_payload
from agents.config_loader import load_project_config
from agents.store import AgentRestoreStore
from ccbd.lifecycle_report_store import CcbdShutdownReportStore, CcbdStartupReportStore
from ccbd.restore_report_store import CcbdRestoreReportStore
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
from ccbd.services.project_namespace import ProjectNamespaceController
from ccbd.services.project_namespace_state import ProjectNamespaceEventStore, ProjectNamespaceStateStore
from ccbd.services.start_policy import CcbdStartPolicyStore
from ccbd.socket_server import CcbdSocketServer
from ccbd.supervision import RuntimeSupervisionLoop
from ccbd.supervisor import RuntimeSupervisor
from fault_injection import FaultInjectionService
from heartbeat import HeartbeatPolicy, HeartbeatStateStore
from project.ids import compute_project_id
from provider_core.catalog import build_default_provider_catalog
from provider_execution.registry import build_default_execution_registry
from provider_execution.service import ExecutionService
from provider_execution.state_store import ExecutionStateStore
from storage.paths import PathLayout

from .handlers import register_handlers

APP_REQUEST_TIMEOUT_S = 0.0
JOB_HEARTBEAT_SILENCE_START_AFTER_S = 600.0
JOB_HEARTBEAT_REPEAT_INTERVAL_S = 600.0


def initialize_app(app, project_root: str | Path, *, clock, pid: int | None) -> None:
    app.project_root = Path(project_root).expanduser().resolve()
    app.project_id = compute_project_id(app.project_root)
    app.paths = PathLayout(app.project_root)
    app.clock = clock
    app.pid = pid or os.getpid()
    app.config = load_project_config(app.project_root).config
    app.config_identity = project_config_identity_payload(app.config)
    keeper_pid = str(os.environ.get('CCB_KEEPER_PID') or '').strip()
    app.keeper_pid = int(keeper_pid) if keeper_pid.isdigit() and int(keeper_pid) > 0 else None
    app.daemon_instance_id = uuid.uuid4().hex
    app.provider_catalog = build_default_provider_catalog()
    app.mount_manager = MountManager(app.paths, clock=app.clock)
    app.restore_report_store = CcbdRestoreReportStore(app.paths)
    app.startup_report_store = CcbdStartupReportStore(app.paths)
    app.shutdown_report_store = CcbdShutdownReportStore(app.paths)
    app.namespace_state_store = ProjectNamespaceStateStore(app.paths)
    app.namespace_event_store = ProjectNamespaceEventStore(app.paths)
    app.start_policy_store = CcbdStartPolicyStore(app.paths)
    app.ownership_guard = OwnershipGuard(app.paths, app.mount_manager, clock=app.clock)
    app.registry = AgentRegistry(app.paths, app.config)
    app.restore_store = AgentRestoreStore(app.paths)
    app.runtime_service = RuntimeService(app.paths, app.registry, app.project_id, app.restore_store, clock=app.clock)
    app.project_namespace = ProjectNamespaceController(app.paths, app.project_id, clock=app.clock)
    app.runtime_supervisor = RuntimeSupervisor(
        project_root=app.project_root,
        project_id=app.project_id,
        paths=app.paths,
        config=app.config,
        registry=app.registry,
        runtime_service=app.runtime_service,
        project_namespace=app.project_namespace,
        clock=app.clock,
    )
    app.runtime_supervision = RuntimeSupervisionLoop(
        project_id=app.project_id,
        layout=app.paths,
        config=app.config,
        registry=app.registry,
        runtime_service=app.runtime_service,
        mount_agent_fn=app._mount_agent_from_policy,
        remount_project_fn=app._remount_project_from_policy,
        clock=app.clock,
        generation_getter=lambda: app.lease.generation if app.lease is not None else None,
    )
    app.snapshot_writer = SnapshotWriter(app.paths, clock=app.clock)
    app.execution_registry = build_default_execution_registry()
    app.fault_injection = FaultInjectionService(app.paths, clock=app.clock)
    app.execution_service = ExecutionService(
        app.execution_registry,
        clock=app.clock,
        state_store=ExecutionStateStore(app.paths),
        fault_injection=app.fault_injection,
    )
    from completion.tracker import CompletionTrackerService

    app.completion_tracker = CompletionTrackerService(
        app.config,
        app.provider_catalog,
        request_timeout_s=APP_REQUEST_TIMEOUT_S,
    )
    app.dispatcher = JobDispatcher(
        app.paths,
        app.config,
        app.registry,
        runtime_service=app.runtime_service,
        execution_service=app.execution_service,
        auto_reply_delivery_on_complete=True,
        require_actionable_runtime_binding_for_execution=True,
        completion_tracker=app.completion_tracker,
        provider_catalog=app.provider_catalog,
        snapshot_writer=app.snapshot_writer,
        clock=app.clock,
    )
    app.heartbeat_state_store = HeartbeatStateStore(app.paths)
    app.job_heartbeat = JobHeartbeatService(
        app.paths,
        policy=HeartbeatPolicy(
            silence_start_after_s=JOB_HEARTBEAT_SILENCE_START_AFTER_S,
            repeat_interval_s=JOB_HEARTBEAT_REPEAT_INTERVAL_S,
        ),
        store=app.heartbeat_state_store,
        clock=app.clock,
    )
    app.health_monitor = HealthMonitor(
        app.registry,
        app.ownership_guard,
        clock=app.clock,
        namespace_state_store=app.namespace_state_store,
    )
    app.socket_server = CcbdSocketServer(app.paths.ccbd_socket_path)
    app.lease = None
    register_handlers(app)


__all__ = ['initialize_app']
