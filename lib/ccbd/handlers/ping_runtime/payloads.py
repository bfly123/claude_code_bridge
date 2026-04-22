from __future__ import annotations

from agents.models import AgentState
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
        'mount_state': _agent_mount_state(runtime, inspection=inspection),
        'runtime_state': runtime.state.value if runtime is not None else 'stopped',
        'health': runtime.health if runtime is not None else inspection.health.value,
        'diagnostics': {
            'ccbd_generation': inspection.generation,
            'last_heartbeat_at': inspection.lease.last_heartbeat_at if inspection.lease else None,
            'desired_state': _inspection_desired_state(inspection),
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
        'mount_state': _inspection_phase(inspection),
        'desired_state': _inspection_desired_state(inspection),
        'health': inspection.health.value,
        'generation': inspection.generation,
        'socket_path': inspection.socket_path if hasattr(inspection, 'socket_path') else (inspection.lease.socket_path if inspection.lease else None),
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
            'last_failure_reason': str(getattr(inspection, 'last_failure_reason', '') or '').strip() or None,
            'shutdown_intent': str(getattr(inspection, 'shutdown_intent', '') or '').strip() or None,
            **execution_summary,
            **restore_summary,
        },
    }


def _inspection_phase(inspection) -> str:
    phase = str(getattr(inspection, 'phase', '') or '').strip()
    if phase:
        return phase
    lease = getattr(inspection, 'lease', None)
    return str(getattr(getattr(lease, 'mount_state', None), 'value', '') or 'unmounted')


def _inspection_desired_state(inspection) -> str | None:
    desired_state = str(getattr(inspection, 'desired_state', '') or '').strip()
    return desired_state or None


def _agent_mount_state(runtime, *, inspection) -> str:
    if runtime is None:
        return _inspection_phase(inspection)
    if runtime.state is AgentState.STARTING:
        return 'starting'
    if runtime.state is AgentState.FAILED:
        return 'failed'
    if runtime.state is AgentState.STOPPED:
        return 'unmounted'
    return 'mounted'


__all__ = ['build_agent_payload', 'build_ccbd_payload']
