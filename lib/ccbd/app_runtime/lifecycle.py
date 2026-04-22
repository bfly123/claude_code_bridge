from __future__ import annotations

import os

from agents.models import AgentState
from ccbd.models import CcbdShutdownReport, CcbdStartupReport, cleanup_summaries_from_objects
from ccbd.services.lifecycle import build_lifecycle, current_socket_inode
from ccbd.stop_flow import build_shutdown_runtime_snapshots


def start(app):
    with app.ownership_guard.startup_lock():
        generation = app.ownership_guard.verify_or_takeover(
            project_id=app.project_id,
            pid=app.pid,
            socket_path=app.paths.ccbd_socket_path,
        )
        app.lease = app.mount_manager.mark_mounted(
            project_id=app.project_id,
            pid=app.pid,
            socket_path=app.paths.ccbd_socket_path,
            generation=generation,
            config_signature=str(app.config_identity['config_signature']),
            keeper_pid=app.keeper_pid,
            daemon_instance_id=app.daemon_instance_id,
        )
        try:
            app.socket_server.listen()
        except Exception as exc:
            app.lease = release_backend_ownership(app)
            _mark_lifecycle_failed(app, failure_reason=str(exc))
            record_startup_report(
                app,
                trigger='daemon_boot',
                status='failed',
                actions_taken=('mount_backend', 'listen_socket_failed'),
                failure_reason=str(exc),
            )
            raise
    try:
        app.dispatcher.restore_running_jobs()
        adopted_agents = _adopt_existing_runtime_authority(app)
        restore_report = app.dispatcher.last_restore_report(project_id=app.project_id)
        if restore_report is not None:
            app.restore_report_store.save(restore_report)
        _mark_lifecycle_mounted(app)
        startup_actions = ['mount_backend', 'listen_socket', 'restore_running_jobs']
        if adopted_agents:
            startup_actions.append(f'adopt_runtime_authority:{",".join(adopted_agents)}')
        record_startup_report(
            app,
            trigger='daemon_boot',
            status='ok',
            actions_taken=tuple(startup_actions),
            restore_summary=restore_report.summary_fields() if restore_report is not None else {},
        )
    except Exception as exc:
        release_backend_ownership(app)
        _mark_lifecycle_failed(app, failure_reason=str(exc))
        record_startup_report(
            app,
            trigger='daemon_boot',
            status='failed',
            actions_taken=('mount_backend', 'listen_socket', 'restore_running_jobs_failed'),
            failure_reason=str(exc),
        )
        raise
    return app.lease


def heartbeat(app):
    app.health_monitor.check_all()
    app.runtime_supervision.reconcile_once()
    app.dispatcher.reconcile_runtime_views()
    app.dispatcher.tick()
    app.dispatcher.poll_completions()
    app.job_heartbeat.tick(app.dispatcher)
    app.lease = app.mount_manager.refresh_heartbeat(
        expected_pid=app.pid,
        expected_daemon_instance_id=app.daemon_instance_id,
    )
    return app.lease


def serve_forever(app, *, poll_interval: float = 0.2) -> None:
    if app.lease is None:
        start(app)
    try:
        app.socket_server.serve_forever(
            poll_interval=effective_poll_interval(poll_interval),
            on_tick=app.heartbeat,
        )
    finally:
        app.lease = release_backend_ownership(app)


def request_shutdown(app) -> None:
    app.lease = release_backend_ownership(app)


def shutdown(app) -> None:
    execute_project_stop(
        app,
        force=True,
        trigger='shutdown',
        reason='shutdown',
        clear_start_policy=True,
    )


def mark_current_daemon_unmounted(app):
    try:
        return app.mount_manager.mark_unmounted(
            expected_pid=app.pid,
            expected_daemon_instance_id=app.daemon_instance_id,
        )
    except RuntimeError:
        return app.mount_manager.load_state()


def release_backend_ownership(app):
    lease = mark_current_daemon_unmounted(app)
    app.socket_server.shutdown()
    _mark_lifecycle_unmounted(app)
    return lease


def execute_project_stop(
    app,
    *,
    force: bool,
    trigger: str,
    reason: str,
    clear_start_policy: bool,
):
    terminated_jobs = ()
    _mark_lifecycle_stopping(app, shutdown_intent=reason)
    try:
        terminated_jobs = app.dispatcher.terminate_nonterminal_jobs(
            shutdown_reason=reason,
            forced=force,
        )
    except Exception:
        terminated_jobs = ()
    try:
        summary = app.runtime_supervisor.stop_all(force=force)
    except Exception as exc:
        record_shutdown_report(
            app,
            trigger=trigger,
            status='failed',
            forced=force,
            reason=reason,
            stopped_agents=(),
            actions_taken=(
                f'terminate_nonterminal_jobs:{len(terminated_jobs)}',
                'stop_all_failed',
            ),
            cleanup_summaries=(),
            failure_reason=str(exc),
        )
        raise

    app.lease = release_backend_ownership(app)
    if clear_start_policy:
        try:
            app.start_policy_store.clear()
        except Exception:
            pass
    record_shutdown_report(
        app,
        trigger=trigger,
        status='ok',
        forced=force,
        reason=reason,
        stopped_agents=tuple(summary.stopped_agents),
        actions_taken=(
            f'terminate_nonterminal_jobs:{len(terminated_jobs)}',
            'request_shutdown',
        ),
        cleanup_summaries=summary.cleanup_summaries,
        failure_reason=None,
    )
    return summary


def record_shutdown_report(
    app,
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
    try:
        inspection = app.ownership_guard.inspect()
        runtime_snapshots = build_shutdown_runtime_snapshots(
            paths=app.paths,
            config=app.config,
            registry=app.registry,
        )
        report = CcbdShutdownReport(
            project_id=app.project_id,
            generated_at=app.clock(),
            trigger=trigger,
            status=status,
            forced=forced,
            stopped_agents=stopped_agents,
            daemon_generation=inspection.generation,
            reason=reason,
            inspection_after=inspection.to_record(),
            actions_taken=actions_taken,
            cleanup_summaries=cleanup_summaries_from_objects(cleanup_summaries),
            runtime_snapshots=runtime_snapshots,
            failure_reason=failure_reason,
        )
        app.shutdown_report_store.save(report)
    except Exception:
        return


def record_startup_report(
    app,
    *,
    trigger: str,
    status: str,
    actions_taken: tuple[str, ...],
    restore_summary: dict[str, object] | None = None,
    failure_reason: str | None = None,
) -> None:
    try:
        inspection = app.ownership_guard.inspect()
        report = CcbdStartupReport(
            project_id=app.project_id,
            generated_at=app.clock(),
            trigger=trigger,
            status=status,
            requested_agents=(),
            desired_agents=tuple(sorted(app.config.agents)),
            restore_requested=False,
            auto_permission=False,
            daemon_generation=app.lease.generation if app.lease is not None else inspection.generation,
            daemon_started=True,
            config_signature=str(app.config_identity.get('config_signature') or '').strip() or None,
            inspection=inspection.to_record(),
            restore_summary=dict(restore_summary or {}),
            actions_taken=actions_taken,
            cleanup_summaries=(),
            agent_results=(),
            failure_reason=failure_reason,
        )
        app.startup_report_store.save(report)
    except Exception:
        return


def effective_poll_interval(poll_interval: float) -> float:
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


def _adopt_existing_runtime_authority(app) -> tuple[str, ...]:
    if app.lease is None:
        return ()
    generation = int(app.lease.generation)
    adopted: list[str] = []
    for runtime in app.registry.list_all():
        if runtime.state not in {AgentState.IDLE, AgentState.BUSY, AgentState.DEGRADED}:
            continue
        current_generation = getattr(runtime, 'daemon_generation', None)
        try:
            current_generation = int(current_generation) if current_generation is not None else None
        except Exception:
            current_generation = None
        if current_generation == generation and runtime.binding_generation == runtime.runtime_generation:
            continue
        app.runtime_service.adopt_runtime_authority(runtime, daemon_generation=generation)
        adopted.append(runtime.agent_name)
    return tuple(adopted)


def _current_lifecycle(app):
    lifecycle = app.lifecycle_store.load()
    if lifecycle is not None:
        return lifecycle
    return build_lifecycle(
        project_id=app.project_id,
        occurred_at=app.clock(),
        desired_state='running',
        phase='unmounted',
        generation=int(getattr(app.lease, 'generation', 0) or 0),
        keeper_pid=app.keeper_pid,
        config_signature=str(app.config_identity.get('config_signature') or '').strip() or None,
        socket_path=str(app.paths.ccbd_socket_path),
    )


def _mark_lifecycle_mounted(app) -> None:
    lifecycle = _current_lifecycle(app)
    namespace_state = app.namespace_state_store.load() if getattr(app, 'namespace_state_store', None) is not None else None
    app.lifecycle_store.save(
        lifecycle.with_phase(
            'mounted',
            occurred_at=app.clock(),
            desired_state='running',
            generation=int(getattr(app.lease, 'generation', 0) or lifecycle.generation),
            keeper_pid=app.keeper_pid,
            owner_pid=app.pid,
            owner_daemon_instance_id=app.daemon_instance_id,
            config_signature=str(app.config_identity.get('config_signature') or '').strip() or lifecycle.config_signature,
            socket_path=str(app.paths.ccbd_socket_path),
            socket_inode=current_socket_inode(app.paths.ccbd_socket_path),
            namespace_epoch=getattr(namespace_state, 'namespace_epoch', None),
            last_failure_reason=None,
            shutdown_intent=None,
        )
    )


def _mark_lifecycle_stopping(app, *, shutdown_intent: str) -> None:
    lifecycle = _current_lifecycle(app)
    app.lifecycle_store.save(
        lifecycle.with_phase(
            'stopping',
            occurred_at=app.clock(),
            desired_state='stopped',
            shutdown_intent=shutdown_intent,
            last_failure_reason=None,
        )
    )


def _mark_lifecycle_unmounted(app) -> None:
    lifecycle = _current_lifecycle(app)
    app.lifecycle_store.save(
        lifecycle.with_phase(
            'unmounted',
            occurred_at=app.clock(),
            owner_pid=None,
            owner_daemon_instance_id=None,
            socket_inode=None,
            socket_path=str(app.paths.ccbd_socket_path),
            namespace_epoch=None,
            last_failure_reason=None,
        )
    )


def _mark_lifecycle_failed(app, *, failure_reason: str) -> None:
    lifecycle = _current_lifecycle(app)
    app.lifecycle_store.save(
        lifecycle.with_phase(
            'failed',
            occurred_at=app.clock(),
            owner_pid=None,
            owner_daemon_instance_id=None,
            socket_inode=None,
            socket_path=str(app.paths.ccbd_socket_path),
            namespace_epoch=None,
            last_failure_reason=failure_reason,
        )
    )


__all__ = [
    'execute_project_stop',
    'heartbeat',
    'mark_current_daemon_unmounted',
    'record_shutdown_report',
    'record_startup_report',
    'release_backend_ownership',
    'request_shutdown',
    'serve_forever',
    'shutdown',
    'start',
]
