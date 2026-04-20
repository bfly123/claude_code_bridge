from __future__ import annotations

from pathlib import Path

from provider_core.contracts import ProviderRuntimeIdentity
from provider_core.registry import build_default_session_binding_map

from .binding import AgentBinding
from .fields import (
    session_file,
    session_id,
    session_ref,
    session_runtime_pid,
    session_runtime_ref,
    session_runtime_root,
    session_terminal,
    session_tmux_socket_name,
    session_tmux_socket_path,
)
from .loading import binding_search_roots, load_provider_session
from .pane import inspect_session_pane
from .validation import session_binding_is_usable


def default_binding_adapter(provider: str):
    return build_default_session_binding_map(include_optional=True).get(str(provider or '').strip().lower())


def resolve_agent_binding(
    *,
    provider: str,
    agent_name: str,
    workspace_path: str | Path,
    project_root: str | Path | None = None,
    ensure_usable: bool = False,
    adapter_resolver=default_binding_adapter,
    sleep_fn,
) -> AgentBinding | None:
    normalized_provider = str(provider or '').strip().lower()
    adapter = adapter_resolver(normalized_provider)
    if adapter is None:
        return None

    search_roots = binding_search_roots(
        workspace_path=Path(workspace_path).expanduser(),
        project_root=Path(project_root).expanduser() if project_root is not None else None,
    )
    session = load_provider_session(
        adapter=adapter,
        provider=normalized_provider,
        agent_name=agent_name,
        roots=search_roots,
        ensure_usable=ensure_usable,
        session_is_usable_fn=lambda candidate: session_binding_is_usable(candidate, sleep_fn=sleep_fn),
    )
    if session is None:
        return None

    pane_details = inspect_session_pane(session)
    if ensure_usable and pane_details['pane_state'] == 'unknown' and pane_details['active_pane_id']:
        pane_details['pane_state'] = 'alive'
    identity = _live_runtime_identity(adapter, session)

    return AgentBinding(
        runtime_ref=session_runtime_ref(session),
        session_ref=session_ref(
            session,
            session_id_attr=adapter.session_id_attr,
            session_path_attr=adapter.session_path_attr,
        ),
        provider=normalized_provider,
        runtime_root=session_runtime_root(session),
        runtime_pid=session_runtime_pid(session, provider=normalized_provider),
        session_file=session_file(session),
        session_id=session_id(session, session_id_attr=adapter.session_id_attr),
        tmux_socket_name=session_tmux_socket_name(session),
        tmux_socket_path=session_tmux_socket_path(session),
        terminal=session_terminal(session),
        pane_id=pane_details['pane_id'],
        active_pane_id=pane_details['active_pane_id'],
        pane_title_marker=pane_details['pane_title_marker'],
        pane_state=pane_details['pane_state'],
        provider_identity_state=getattr(identity, 'state', None) if identity is not None else None,
        provider_identity_reason=getattr(identity, 'reason', None) if identity is not None else None,
    )


def _live_runtime_identity(adapter, session):
    identity_fn = getattr(adapter, 'live_runtime_identity', None)
    if not callable(identity_fn):
        return None
    try:
        return identity_fn(session)
    except Exception:
        return ProviderRuntimeIdentity('unknown', 'provider_identity_probe_failed')


__all__ = ['default_binding_adapter', 'resolve_agent_binding']
