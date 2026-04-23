from __future__ import annotations

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


def register_handlers(app) -> None:
    app.socket_server.register_handler('submit', build_submit_handler(app.dispatcher))
    app.socket_server.register_handler('get', build_get_handler(app.dispatcher, health_monitor=app.health_monitor))
    app.socket_server.register_handler('watch', build_watch_handler(app.dispatcher, health_monitor=app.health_monitor))
    app.socket_server.register_handler('queue', build_queue_handler(app.dispatcher))
    app.socket_server.register_handler('trace', build_trace_handler(app.dispatcher))
    app.socket_server.register_handler('resubmit', build_resubmit_handler(app.dispatcher))
    app.socket_server.register_handler('retry', build_retry_handler(app.dispatcher))
    app.socket_server.register_handler('inbox', build_inbox_handler(app.dispatcher))
    app.socket_server.register_handler('ack', build_ack_handler(app.dispatcher))
    app.socket_server.register_handler('cancel', build_cancel_handler(app.dispatcher))
    app.socket_server.register_handler(
        'ping',
        build_ping_handler(
            project_id=app.project_id,
            config=app.config,
            paths=app.paths,
            registry=app.registry,
            health_monitor=app.health_monitor,
            execution_state_store=app.execution_service._state_store,
            execution_registry=app.execution_registry,
            restore_report_store=app.restore_report_store,
            namespace_state_store=app.namespace_state_store,
            namespace_event_store=app.namespace_event_store,
            start_policy_store=app.start_policy_store,
        ),
    )
    app.socket_server.register_handler('attach', build_attach_handler(app.runtime_service))
    app.socket_server.register_handler('start', build_start_handler(app))
    app.socket_server.register_handler('restore', build_restore_handler(app.runtime_service))
    app.socket_server.register_handler('stop-all', build_stop_all_handler(app))
    app.socket_server.register_handler('shutdown', build_shutdown_handler(app))


__all__ = ['register_handlers']
