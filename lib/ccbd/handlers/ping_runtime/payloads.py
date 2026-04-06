from __future__ import annotations

from agents.config_identity import project_config_identity_payload
from provider_execution.capabilities import execution_restore_capability


def build_agent_payload(*, project_id: str, agent_name: str, registry, inspection, execution_registry) -> dict:
    spec = registry.spec_for(agent_name)
    runtime = registry.get(agent_name)
    adapter = execution_registry.get(spec.provider) if execution_registry is not None else None
    capability = execution_restore_capability(adapter, provider=spec.provider)
    return {
        'project_id': project_id,
        'agent_name': spec.name,
        'provider': spec.provider,
        'mount_state': inspection.lease.mount_state.value if inspection.lease is not None else 'unmounted',
        'runtime_state': runtime.state.value if runtime is not None else 'stopped',
        'health': runtime.health if runtime is not None else inspection.health.value,
        'diagnostics': {
            'ccbd_generation': inspection.generation,
            'last_heartbeat_at': inspection.lease.last_heartbeat_at if inspection.lease else None,
            **capability,
        },
    }


def build_ccbd_payload(
    *,
    project_id: str,
    config,
    inspection,
    execution_summary: dict,
    restore_summary: dict,
    namespace_summary: dict,
    namespace_event_summary: dict,
    start_policy_summary: dict,
) -> dict:
    identity = project_config_identity_payload(config)
    return {
        'project_id': project_id,
        'mount_state': inspection.lease.mount_state.value if inspection.lease is not None else 'unmounted',
        'health': inspection.health.value,
        'generation': inspection.generation,
        'socket_path': inspection.lease.socket_path if inspection.lease else None,
        'known_agents': list(identity['known_agents']),
        'config_signature': identity['config_signature'],
        **namespace_summary,
        **namespace_event_summary,
        **start_policy_summary,
        'diagnostics': {
            'pid_alive': inspection.pid_alive,
            'socket_connectable': inspection.socket_connectable,
            'heartbeat_fresh': inspection.heartbeat_fresh,
            'takeover_allowed': inspection.takeover_allowed,
            'reason': inspection.reason,
            **execution_summary,
            **restore_summary,
        },
    }


__all__ = ['build_agent_payload', 'build_ccbd_payload']
