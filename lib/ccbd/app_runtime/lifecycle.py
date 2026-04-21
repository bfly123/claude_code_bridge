from __future__ import annotations

import os

from ccbd.models import CcbdShutdownReport, CcbdStartupReport, cleanup_summaries_from_objects
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
        restore_report = app.dispatcher.last_restore_report(project_id=app.project_id)
        if restore_report is not None:
            app.restore_report_store.save(restore_report)
        record_startup_report(
            app,
            trigger='daemon_boot',
            status='ok',
            actions_taken=('mount_backend', 'listen_socket', 'restore_running_jobs'),
            restore_summary=restore_report.summary_fields() if restore_report is not None else {},
        )
    except Exception as exc:
        release_backend_ownership(app)
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
    return lease


def execute_project_stop(
    app,
    *,
    force: bool,
    trigger: str,
    reason: str,
    clear_start_policy: bool,
):
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
            actions_taken=('stop_all_failed',),
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
        actions_taken=('request_shutdown',),
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
