from __future__ import annotations

from .stores import report_summary_fields, safe_report_load


def ccbd_summary(*, local, stores: dict[str, object], errors: list[str]) -> dict:
    return {
        'state': local.mount_state,
        'pid': None,
        'socket_path': local.socket_path,
        'generation': local.generation,
        'health': local.health,
        'last_heartbeat_at': local.last_heartbeat_at,
        'pid_alive': local.pid_alive,
        'socket_connectable': local.socket_connectable,
        'heartbeat_fresh': local.heartbeat_fresh,
        'takeover_allowed': local.takeover_allowed,
        'reason': local.reason,
        **stores['execution_state'].summary(),
        **report_summary_fields(safe_report_load(stores['restore_report'].load, errors, label='restore_report')),
        **report_summary_fields(safe_report_load(stores['startup_report'].load, errors, label='startup_report')),
        **report_summary_fields(safe_report_load(stores['shutdown_report'].load, errors, label='shutdown_report')),
        **report_summary_fields(safe_report_load(stores['namespace_state'].load, errors, label='namespace_state')),
        **report_summary_fields(safe_report_load(stores['namespace_event'].load_latest, errors, label='namespace_event')),
        **report_summary_fields(safe_report_load(stores['start_policy'].load, errors, label='start_policy')),
        **report_summary_fields(safe_report_load(stores['tmux_cleanup'].load_latest, errors, label='tmux_cleanup')),
        'diagnostic_errors': errors,
    }


__all__ = ['ccbd_summary']
