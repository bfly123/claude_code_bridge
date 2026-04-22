from __future__ import annotations

from .payloads import build_agent_payload, build_ccbd_payload
from .summaries import (
    load_namespace_event_summary,
    load_namespace_summary,
    load_restore_summary,
    load_start_policy_summary,
)


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
    def handle(payload: dict) -> dict:
        target = str(payload.get('target') or '').strip().lower()
        if target == 'all':
            health_monitor.check_all()
        elif target not in {'', 'ccbd'}:
            runtime = registry.get(target)
            if runtime is not None:
                health_monitor._runtime_health(runtime)
        inspection = health_monitor.daemon_health()
        execution_summary = execution_state_store.summary() if execution_state_store is not None else {}
        restore_summary = load_restore_summary(restore_report_store)
        namespace_summary = load_namespace_summary(namespace_state_store)
        namespace_event_summary = load_namespace_event_summary(namespace_event_store)
        start_policy_summary = load_start_policy_summary(start_policy_store)
        if target in {'', 'ccbd'}:
            return build_ccbd_payload(
                project_id=project_id,
                config=config,
                inspection=inspection,
                execution_summary=execution_summary,
                restore_summary=restore_summary,
                namespace_summary=namespace_summary,
                namespace_event_summary=namespace_event_summary,
                start_policy_summary=start_policy_summary,
            )
        if target == 'all':
            return {
                'project_id': project_id,
                'ccbd_state': inspection.lease.mount_state.value if inspection.lease is not None else 'unmounted',
                'agents': [
                    build_agent_payload(
                        project_id=project_id,
                        agent_name=name,
                        registry=registry,
                        inspection=inspection,
                        execution_registry=execution_registry,
                    )
                    for name in registry.list_known_agents()
                ],
            }
        return build_agent_payload(
            project_id=project_id,
            agent_name=target,
            registry=registry,
            inspection=inspection,
            execution_registry=execution_registry,
        )

    return handle


__all__ = ['build_ping_handler']
