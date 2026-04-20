from __future__ import annotations

from collections.abc import Mapping

from .ops_views_common import binding_line


def render_doctor(payload: Mapping[str, object]) -> tuple[str, ...]:
    installation = payload.get('installation') or {}
    requirements = payload.get('requirements') or {}
    ccbd = payload['ccbd']
    lines = [
        f'project: {payload["project"]}',
        f'project_id: {payload["project_id"]}',
        f'install_path: {installation.get("path")}',
        f'install_mode: {installation.get("install_mode")}',
        f'install_source_kind: {installation.get("source_kind")}',
        f'install_version: {installation.get("version")}',
        f'install_channel: {installation.get("channel")}',
        f'install_build_time: {installation.get("build_time")}',
        f'install_platform: {installation.get("platform")}',
        f'install_arch: {installation.get("arch")}',
        f'requirement_python_executable: {requirements.get("python_executable")}',
        f'requirement_python_version: {requirements.get("python_version")}',
        f'requirement_tmux_available: {requirements.get("tmux_available")}',
        f'requirement_tmux_path: {requirements.get("tmux_path")}',
        f'ccbd_state: {ccbd["state"]}',
        f'ccbd_health: {ccbd["health"]}',
        f'ccbd_generation: {ccbd["generation"]}',
        f'ccbd_last_heartbeat_at: {ccbd["last_heartbeat_at"]}',
        f'ccbd_pid_alive: {ccbd["pid_alive"]}',
        f'ccbd_socket_connectable: {ccbd["socket_connectable"]}',
        f'ccbd_heartbeat_fresh: {ccbd["heartbeat_fresh"]}',
        f'ccbd_takeover_allowed: {ccbd["takeover_allowed"]}',
        f'ccbd_reason: {ccbd["reason"]}',
        f'ccbd_active_execution_count: {ccbd["active_execution_count"]}',
        f'ccbd_recoverable_execution_count: {ccbd["recoverable_execution_count"]}',
        f'ccbd_nonrecoverable_execution_count: {ccbd["nonrecoverable_execution_count"]}',
        f'ccbd_pending_items_count: {ccbd["pending_items_count"]}',
        f'ccbd_terminal_pending_count: {ccbd["terminal_pending_count"]}',
        f'ccbd_recoverable_execution_providers: {ccbd["recoverable_execution_providers"]}',
        f'ccbd_nonrecoverable_execution_providers: {ccbd["nonrecoverable_execution_providers"]}',
        f'ccbd_last_restore_at: {ccbd.get("last_restore_at")}',
        f'ccbd_last_restore_running_job_count: {ccbd.get("last_restore_running_job_count")}',
        f'ccbd_last_restore_restored_execution_count: {ccbd.get("last_restore_restored_execution_count")}',
        f'ccbd_last_restore_replay_pending_count: {ccbd.get("last_restore_replay_pending_count")}',
        f'ccbd_last_restore_terminal_pending_count: {ccbd.get("last_restore_terminal_pending_count")}',
        f'ccbd_last_restore_abandoned_execution_count: {ccbd.get("last_restore_abandoned_execution_count")}',
        f'ccbd_last_restore_already_active_count: {ccbd.get("last_restore_already_active_count")}',
        f'ccbd_last_restore_results_text: {ccbd.get("last_restore_results_text")}',
        f'ccbd_startup_last_at: {ccbd.get("startup_last_at")}',
        f'ccbd_startup_last_trigger: {ccbd.get("startup_last_trigger")}',
        f'ccbd_startup_last_status: {ccbd.get("startup_last_status")}',
        f'ccbd_startup_last_generation: {ccbd.get("startup_last_generation")}',
        f'ccbd_startup_last_daemon_started: {ccbd.get("startup_last_daemon_started")}',
        f'ccbd_startup_last_requested_agents: {ccbd.get("startup_last_requested_agents")}',
        f'ccbd_startup_last_desired_agents: {ccbd.get("startup_last_desired_agents")}',
        f'ccbd_startup_last_actions: {ccbd.get("startup_last_actions")}',
        f'ccbd_startup_last_cleanup_killed: {ccbd.get("startup_last_cleanup_killed")}',
        f'ccbd_startup_last_failure_reason: {ccbd.get("startup_last_failure_reason")}',
        f'ccbd_startup_last_agent_results_text: {ccbd.get("startup_last_agent_results_text")}',
        f'ccbd_shutdown_last_at: {ccbd.get("shutdown_last_at")}',
        f'ccbd_shutdown_last_trigger: {ccbd.get("shutdown_last_trigger")}',
        f'ccbd_shutdown_last_status: {ccbd.get("shutdown_last_status")}',
        f'ccbd_shutdown_last_forced: {ccbd.get("shutdown_last_forced")}',
        f'ccbd_shutdown_last_generation: {ccbd.get("shutdown_last_generation")}',
        f'ccbd_shutdown_last_reason: {ccbd.get("shutdown_last_reason")}',
        f'ccbd_shutdown_last_stopped_agents: {ccbd.get("shutdown_last_stopped_agents")}',
        f'ccbd_shutdown_last_actions: {ccbd.get("shutdown_last_actions")}',
        f'ccbd_shutdown_last_cleanup_killed: {ccbd.get("shutdown_last_cleanup_killed")}',
        f'ccbd_shutdown_last_failure_reason: {ccbd.get("shutdown_last_failure_reason")}',
        f'ccbd_shutdown_last_runtime_states_text: {ccbd.get("shutdown_last_runtime_states_text")}',
        f'ccbd_namespace_epoch: {ccbd.get("namespace_epoch")}',
        f'ccbd_namespace_tmux_socket_path: {ccbd.get("namespace_tmux_socket_path")}',
        f'ccbd_namespace_tmux_session_name: {ccbd.get("namespace_tmux_session_name")}',
        f'ccbd_namespace_layout_version: {ccbd.get("namespace_layout_version")}',
        f'ccbd_namespace_ui_attachable: {ccbd.get("namespace_ui_attachable")}',
        f'ccbd_namespace_last_started_at: {ccbd.get("namespace_last_started_at")}',
        f'ccbd_namespace_last_destroyed_at: {ccbd.get("namespace_last_destroyed_at")}',
        f'ccbd_namespace_last_destroy_reason: {ccbd.get("namespace_last_destroy_reason")}',
        f'ccbd_namespace_last_event_kind: {ccbd.get("namespace_last_event_kind")}',
        f'ccbd_namespace_last_event_at: {ccbd.get("namespace_last_event_at")}',
        f'ccbd_namespace_last_event_epoch: {ccbd.get("namespace_last_event_epoch")}',
        f'ccbd_namespace_last_event_socket_path: {ccbd.get("namespace_last_event_socket_path")}',
        f'ccbd_namespace_last_event_session_name: {ccbd.get("namespace_last_event_session_name")}',
        f'ccbd_start_policy_auto_permission: {ccbd.get("start_policy_auto_permission")}',
        f'ccbd_start_policy_recovery_restore: {ccbd.get("start_policy_recovery_restore")}',
        f'ccbd_start_policy_last_started_at: {ccbd.get("start_policy_last_started_at")}',
        f'ccbd_start_policy_source: {ccbd.get("start_policy_source")}',
        f'ccbd_tmux_cleanup_last_kind: {ccbd.get("tmux_cleanup_last_kind")}',
        f'ccbd_tmux_cleanup_last_at: {ccbd.get("tmux_cleanup_last_at")}',
        f'ccbd_tmux_cleanup_socket_count: {ccbd.get("tmux_cleanup_socket_count")}',
        f'ccbd_tmux_cleanup_total_owned: {ccbd.get("tmux_cleanup_total_owned")}',
        f'ccbd_tmux_cleanup_total_active: {ccbd.get("tmux_cleanup_total_active")}',
        f'ccbd_tmux_cleanup_total_orphaned: {ccbd.get("tmux_cleanup_total_orphaned")}',
        f'ccbd_tmux_cleanup_total_killed: {ccbd.get("tmux_cleanup_total_killed")}',
        f'ccbd_tmux_cleanup_sockets: {ccbd.get("tmux_cleanup_sockets")}',
    ]
    for provider in requirements.get('provider_commands') or ():
        lines.append(
            'requirement_provider: '
            f'name={provider.get("provider")} '
            f'executable={provider.get("executable")} '
            f'available={provider.get("available")} '
            f'path={provider.get("path")}'
        )
    for error in ccbd.get('diagnostic_errors') or ():
        lines.append(f'ccbd_diagnostic_error: {error}')
    for agent in payload['agents']:
        lines.append(
            f'agent: name={agent["agent_name"]} health={agent["health"]} provider={agent["provider"]} completion={agent["completion_family"]}'
        )
        lines.append(binding_line(agent))
        lines.append(
            f'restore: supported={agent["execution_resume_supported"]} mode={agent["execution_restore_mode"]} reason={agent["execution_restore_reason"]}'
        )
        lines.append(f'restore_detail: {agent["execution_restore_detail"]}')
    return tuple(lines)


__all__ = ['render_doctor']
