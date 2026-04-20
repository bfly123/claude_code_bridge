from __future__ import annotations


def provider_pane_health(monitor, runtime) -> str | None:
    assessment = monitor._assess_provider_pane(
        runtime=runtime,
        registry=monitor._registry,
        session_bindings=monitor._session_bindings,
        namespace_state_store=monitor._namespace_state_store,
    )
    if assessment is None:
        return None

    if assessment.session is None:
        updated = monitor._mark_degraded(runtime, health=assessment.health)
        return updated.health

    if assessment.terminal != 'tmux':
        refreshed = monitor._rebind_runtime(runtime, assessment.session, assessment.binding)
        return refreshed.health

    if assessment.health == 'healthy':
        refreshed = monitor._rebind_runtime(runtime, assessment.session, assessment.binding)
        return refreshed.health
    updated = monitor._mark_degraded(
        runtime,
        health=assessment.health,
        session=assessment.session,
        binding=assessment.binding,
    )
    return updated.health


__all__ = ['provider_pane_health']
