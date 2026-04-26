from __future__ import annotations

import os

from ccbd.models import CcbdStartupReport


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
            app.lease = app.mount_manager.mark_unmounted()
            app.socket_server.shutdown()
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
        request_shutdown(app)
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
    app.lease = app.mount_manager.refresh_heartbeat()
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
        app.lease = app.mount_manager.mark_unmounted()
        app.socket_server.shutdown()


def request_shutdown(app) -> None:
    app.lease = app.mount_manager.mark_unmounted()
    app.socket_server.shutdown()


def shutdown(app, *, reason: str = 'shutdown') -> None:
    try:
        app.runtime_supervisor.stop_all(force=True)
    except Exception:
        pass
    request_shutdown(app)


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


__all__ = ['heartbeat', 'record_startup_report', 'request_shutdown', 'serve_forever', 'shutdown', 'start']
