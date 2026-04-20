from __future__ import annotations

from dataclasses import replace

from agents.models import AgentState
from provider_core.session_binding_evidence import session_ref

from .common import pane_state_for_health, runtime_fields_from_facts, runtime_fields_from_session


def mark_degraded(monitor, runtime, *, health: str, session=None, binding=None):
    updated_fields: dict[str, object] = {}
    if session is not None:
        facts = monitor._provider_runtime_facts(runtime, session, binding) if binding is not None else None
        if facts is not None:
            updated_fields = runtime_fields_from_facts(runtime, facts)
            if facts.session_ref:
                updated_fields['session_ref'] = facts.session_ref
        else:
            updated_fields = runtime_fields_from_session(runtime, session, binding)
            if binding is not None:
                bound_session_ref = session_ref(
                    session,
                    session_id_attr=binding.session_id_attr,
                    session_path_attr=binding.session_path_attr,
                )
                if bound_session_ref:
                    updated_fields['session_ref'] = bound_session_ref
    next_pane_id = str(updated_fields.get('pane_id') or runtime.pane_id or '').strip() or None
    next_pane_state, next_active_pane_id = pane_state_for_health(runtime, health, pane_id=next_pane_id)
    updated = replace(
        runtime,
        state=AgentState.DEGRADED,
        health=health,
        pane_state=next_pane_state,
        active_pane_id=next_active_pane_id,
        last_seen_at=monitor._clock(),
        **updated_fields,
    )
    return monitor._registry.upsert(updated)


__all__ = ['mark_degraded']
