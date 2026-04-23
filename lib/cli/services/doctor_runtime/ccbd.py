from __future__ import annotations

from .stores import report_summary_fields, safe_report_load


def ccbd_summary(*, local, stores: dict[str, object], errors: list[str]) -> dict:
    ipc_state = safe_report_load(stores['ipc_state'].load, errors, label='ipc_state')
    ipc_summary = _ipc_summary(ipc_state)
    return {
        'state': local.mount_state,
        'pid': None,
        'socket_path': local.socket_path,
        'ipc_kind': local.ipc_kind or ipc_summary.get('ipc_kind'),
        'ipc_ref': ipc_summary.get('ipc_ref'),
        'ipc_state': ipc_summary.get('ipc_state'),
        'ipc_updated_at': ipc_summary.get('ipc_updated_at'),
        'backend_family': local.backend_family or ipc_summary.get('backend_family'),
        'backend_impl': local.backend_impl or ipc_summary.get('backend_impl'),
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


def _ipc_summary(payload) -> dict:
    fields = report_summary_fields(payload)
    if not fields:
        return {}
    return {
        'ipc_kind': fields.get('ipc_kind'),
        'ipc_ref': fields.get('ipc_ref'),
        'ipc_state': fields.get('state'),
        'ipc_updated_at': fields.get('updated_at'),
        'backend_family': fields.get('backend_family'),
        'backend_impl': fields.get('backend_impl'),
    }


__all__ = ['ccbd_summary']
