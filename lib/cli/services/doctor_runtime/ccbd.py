from __future__ import annotations

from .stores import report_summary_fields, safe_report_load


def ccbd_summary(*, local, stores: dict[str, object], errors: list[str]) -> dict:
    return {
        'state': local.mount_state,
        'pid': None,
        'socket_path': local.socket_path,
        'preferred_socket_path': local.preferred_socket_path,
        'effective_socket_path': local.effective_socket_path,
        'socket_root_kind': local.socket_root_kind,
        'socket_fallback_reason': local.socket_fallback_reason,
        'socket_filesystem_hint': local.socket_filesystem_hint,
        'tmux_socket_path': local.tmux_socket_path,
        'tmux_preferred_socket_path': local.tmux_preferred_socket_path,
        'tmux_effective_socket_path': local.tmux_effective_socket_path,
        'tmux_socket_root_kind': local.tmux_socket_root_kind,
        'tmux_socket_fallback_reason': local.tmux_socket_fallback_reason,
        'tmux_socket_filesystem_hint': local.tmux_socket_filesystem_hint,
        'generation': local.generation,
        'health': local.health,
        'last_heartbeat_at': local.last_heartbeat_at,
        'pid_alive': local.pid_alive,
        'socket_connectable': local.socket_connectable,
        'heartbeat_fresh': local.heartbeat_fresh,
        'takeover_allowed': local.takeover_allowed,
        'reason': local.reason,
        'startup_id': local.startup_id,
        'startup_stage': local.startup_stage,
        'last_progress_at': local.last_progress_at,
        'startup_deadline_at': local.startup_deadline_at,
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
