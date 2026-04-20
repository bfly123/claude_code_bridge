from __future__ import annotations

from typing import Any, Dict

from provider_core.runtime_specs import parse_qualified_provider
from terminal_runtime import get_backend_for_session
def get_providers_map(data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    providers = data.get("providers")
    if not isinstance(providers, dict):
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for key, value in providers.items():
        if isinstance(key, str) and isinstance(value, dict):
            out[key.strip().lower()] = dict(value)
    return out


def provider_pane_alive(
    record: Dict[str, Any],
    provider: str,
    *,
    get_backend_for_session_fn=get_backend_for_session,
) -> bool:
    base_provider, _ = parse_qualified_provider(provider)
    providers = get_providers_map(record)
    entry = providers.get((provider or "").strip().lower())
    if not isinstance(entry, dict):
        entry = providers.get(base_provider)
    if not isinstance(entry, dict):
        return False

    pane_id = str(entry.get("pane_id") or "").strip()

    try:
        backend = get_backend_for_session_fn({"terminal": record.get("terminal", "tmux")})
    except Exception:
        backend = None
    if not backend or not pane_id:
        return False

    try:
        return bool(backend.is_alive(pane_id))
    except Exception:
        return False

__all__ = ["get_providers_map", "provider_pane_alive"]
