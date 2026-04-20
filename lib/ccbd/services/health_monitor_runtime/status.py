from __future__ import annotations

from dataclasses import replace

from agents.models import AgentState, RuntimeBindingSource, normalize_runtime_binding_source


def daemon_health(monitor):
    return monitor._ownership_guard.inspect()


def check_all(monitor) -> dict[str, str]:
    statuses: dict[str, str] = {}
    for runtime in monitor._registry.list_all():
        status = monitor._runtime_health(runtime)
        statuses[runtime.agent_name] = status
    return statuses


def collect_orphans(monitor) -> tuple[str, ...]:
    statuses = monitor.check_all()
    return tuple(sorted(name for name, status in statuses.items() if status != 'healthy'))


def runtime_health(monitor, runtime) -> str:
    binding_source = normalize_runtime_binding_source(
        getattr(runtime, 'binding_source', RuntimeBindingSource.PROVIDER_SESSION)
    )
    if runtime.state in {AgentState.STOPPED, AgentState.FAILED}:
        return runtime.health
    pane_status = monitor._pane_health(runtime)
    if pane_status is not None:
        return pane_status
    if runtime.pid is not None and not monitor._pid_exists(runtime.pid):
        updated = replace(runtime, state=AgentState.DEGRADED, health='orphaned', last_seen_at=monitor._clock())
        monitor._registry.upsert(updated)
        return updated.health
    if binding_source is RuntimeBindingSource.EXTERNAL_ATTACH:
        return runtime.health
    if runtime.state is AgentState.DEGRADED:
        return runtime.health
    if runtime.health not in {'healthy', 'restored'}:
        updated = replace(runtime, health='healthy', last_seen_at=monitor._clock())
        monitor._registry.upsert(updated)
        return updated.health
    return runtime.health


def pane_health(monitor, runtime) -> str | None:
    binding_source = normalize_runtime_binding_source(
        getattr(runtime, 'binding_source', RuntimeBindingSource.PROVIDER_SESSION)
    )
    if binding_source is RuntimeBindingSource.EXTERNAL_ATTACH:
        return None
    return monitor._provider_pane_health(runtime)


__all__ = [
    'check_all',
    'collect_orphans',
    'daemon_health',
    'pane_health',
    'runtime_health',
]
