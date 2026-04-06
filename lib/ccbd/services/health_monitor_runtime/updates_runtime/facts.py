from __future__ import annotations

from ccbd.services.provider_runtime_facts import build_provider_runtime_facts


def provider_runtime_facts(monitor, runtime, session, binding, *, pane_id_override: str | None = None):
    provider = str(getattr(runtime, 'provider', '') or '').strip()
    if not provider:
        try:
            provider = str(monitor._registry.spec_for(runtime.agent_name).provider or '').strip()
        except Exception:
            provider = ''
    if not provider:
        return None
    try:
        return build_provider_runtime_facts(
            session,
            binding=binding,
            provider=provider,
            pane_id_override=pane_id_override,
        )
    except Exception:
        return None


__all__ = ['provider_runtime_facts']
