from __future__ import annotations

from ccbd.models import LeaseHealth
from cli.context import CliContext
from cli.models import ParsedPingCommand

from .daemon import connect_mounted_daemon, ping_local_state


def ping_target(context: CliContext, command: ParsedPingCommand) -> dict:
    local = ping_local_state(context)
    target = command.target
    if local.mount_state == 'unmounted':
        if target == 'ccbd':
            return {
                'project_id': local.project_id,
                'mount_state': local.mount_state,
                'health': local.health,
                'generation': local.generation,
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
                'last_heartbeat_at': local.last_heartbeat_at,
                'pid_alive': local.pid_alive,
                'socket_connectable': local.socket_connectable,
                'heartbeat_fresh': local.heartbeat_fresh,
                'takeover_allowed': local.takeover_allowed,
                'reason': local.reason,
            }
        return {
            'project_id': local.project_id,
            'agent_name': target,
            'provider': None,
            'mount_state': local.mount_state,
            'runtime_state': 'stopped',
            'health': 'unmounted',
            'diagnostics': {'reason': local.reason},
        }
    handle = connect_mounted_daemon(context, allow_restart_stale=True)
    assert handle.client is not None
    payload = handle.client.ping(target)
    if target == 'ccbd':
        diagnostics = dict(payload.pop('diagnostics', {}) or {})
        payload.update(diagnostics)
    return payload
