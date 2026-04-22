from __future__ import annotations

import os
from pathlib import Path

from ccbd.models import CcbdStartupReport, MountState


def start(app, *, defer_post_listen: bool = False):
    app._startup_completed = False
    _mount_and_listen(app)
    if defer_post_listen:
        return app.lease
    _complete_startup(app)
    return app.lease


def _mount_and_listen(app) -> None:
    with app.ownership_guard.startup_lock():
        generation = app.ownership_guard.verify_or_takeover(
            project_id=app.project_id,
            pid=app.pid,
            socket_path=app.paths.ccbd_ipc_ref,
        )
        app.ipc_state_store.save(
            ipc_kind=app.paths.ccbd_ipc_kind,
            ipc_ref=app.paths.ccbd_ipc_ref,
            backend_family=app.namespace_backend_family,
            backend_impl=app.namespace_backend_impl,
            state='mounting',
            updated_at=app.clock(),
        )
        app.lease = app.mount_manager.mark_mounted(
            project_id=app.project_id,
            pid=app.pid,
            socket_path=app.paths.ccbd_ipc_ref,
            ipc_kind=app.paths.ccbd_ipc_kind,
            generation=generation,
            config_signature=str(app.config_identity['config_signature']),
            keeper_pid=app.keeper_pid,
            daemon_instance_id=app.daemon_instance_id,
            backend_family=app.namespace_backend_family,
            backend_impl=app.namespace_backend_impl,
        )
        try:
            app.socket_server.listen()
            app.ipc_state_store.save(
                ipc_kind=app.paths.ccbd_ipc_kind,
                ipc_ref=app.paths.ccbd_ipc_ref,
                backend_family=app.namespace_backend_family,
                backend_impl=app.namespace_backend_impl,
                state='mounted',
                updated_at=app.clock(),
            )
        except Exception as exc:
            app.lease = app.mount_manager.mark_unmounted()
            app.socket_server.shutdown()
            app.ipc_state_store.save(
                ipc_kind=app.paths.ccbd_ipc_kind,
                ipc_ref=app.paths.ccbd_ipc_ref,
                backend_family=app.namespace_backend_family,
                backend_impl=app.namespace_backend_impl,
                state='unmounted',
                updated_at=app.clock(),
            )
            _cleanup_ipc_endpoint(app)
            record_startup_report(
                app,
                trigger='daemon_boot',
                status='failed',
                actions_taken=('mount_backend', 'listen_socket_failed'),
                failure_reason=str(exc),
            )
            raise


def _complete_startup(app) -> None:
    if getattr(app, '_startup_completed', False):
        return
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
        app._startup_completed = True
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
    if app.lease is None or app.lease.mount_state is not MountState.MOUNTED:
        start(app, defer_post_listen=app.paths.ccbd_ipc_kind != 'named_pipe')
    try:
        if app.paths.ccbd_ipc_kind == 'named_pipe' and not getattr(app, '_startup_completed', False):
            _complete_startup(app)
        app.socket_server.serve_forever(
            poll_interval=effective_poll_interval(poll_interval),
            on_tick=_serve_tick(app),
        )
    finally:
        app._startup_completed = False
        app.lease = app.mount_manager.mark_unmounted()
        app.socket_server.shutdown()


def _serve_tick(app):
    def _tick():
        if not getattr(app, '_startup_completed', False):
            _complete_startup(app)
        return app.heartbeat()

    return _tick


def request_shutdown(app) -> None:
    app._startup_completed = False
    app.lease = app.mount_manager.mark_unmounted()
    app.socket_server.shutdown()
    app.ipc_state_store.save(
        ipc_kind=app.paths.ccbd_ipc_kind,
        ipc_ref=app.paths.ccbd_ipc_ref,
        backend_family=app.namespace_backend_family,
        backend_impl=app.namespace_backend_impl,
        state='unmounted',
        updated_at=app.clock(),
    )
    _cleanup_ipc_endpoint(app)


def shutdown(app) -> None:
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


def _cleanup_ipc_endpoint(app) -> None:
    if getattr(app.paths, 'ccbd_ipc_kind', None) != 'unix_socket':
        return
    targets = [getattr(app.paths, 'ccbd_ipc_ref', None), getattr(app.paths, 'ccbd_socket_path', None)]
    for target in targets:
        if not target:
            continue
        try:
            Path(str(target)).unlink(missing_ok=True)
        except Exception:
            pass


__all__ = ['heartbeat', 'record_startup_report', 'request_shutdown', 'serve_forever', 'shutdown', 'start']
