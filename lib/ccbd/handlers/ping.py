from __future__ import annotations

from agents.config_identity import project_config_identity_payload
from provider_execution.capabilities import execution_restore_capability


def build_ping_handler(
    *,
    project_id: str,
    config,
    registry,
    health_monitor,
    execution_state_store=None,
    execution_registry=None,
    restore_report_store=None,
    namespace_state_store=None,
    namespace_event_store=None,
    start_policy_store=None,
):
    def _agent_payload(agent_name: str, inspection) -> dict:
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

    def handle(payload: dict) -> dict:
        target = str(payload.get('target') or '').strip().lower()
        health_monitor.check_all()
        inspection = health_monitor.daemon_health()
        execution_summary = execution_state_store.summary() if execution_state_store is not None else {}
        restore_summary = {}
        namespace_summary = {}
        namespace_event_summary = {}
        start_policy_summary = {}
        identity = project_config_identity_payload(config)
        if restore_report_store is not None:
            report = restore_report_store.load()
            if report is not None:
                restore_summary = report.summary_fields()
        if namespace_state_store is not None:
            state = namespace_state_store.load()
            if state is not None:
                namespace_summary = state.summary_fields()
        if namespace_event_store is not None:
            event = namespace_event_store.load_latest()
            if event is not None:
                namespace_event_summary = event.summary_fields()
        if start_policy_store is not None:
            try:
                policy = start_policy_store.load()
            except Exception:
                policy = None
            if policy is not None:
                start_policy_summary = policy.summary_fields()
        if target in {'', 'ccbd'}:
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
        if target == 'all':
            return {
                'project_id': project_id,
                'ccbd_state': inspection.lease.mount_state.value if inspection.lease is not None else 'unmounted',
                'agents': [_agent_payload(name, inspection) for name in registry.list_known_agents()],
            }
        return _agent_payload(target, inspection)

    return handle
