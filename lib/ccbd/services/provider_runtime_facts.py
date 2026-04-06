from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from provider_core.instance_resolution import named_agent_instance
from provider_core.session_binding_evidence import (
    session_file,
    session_id,
    session_pane_title_marker,
    session_ref,
    session_runtime_pid,
    session_runtime_ref,
    session_runtime_root,
    session_terminal,
    session_tmux_socket_name,
    session_tmux_socket_path,
)


@dataclass(frozen=True)
class ProviderRuntimeFacts:
    runtime_ref: str | None
    session_ref: str | None
    runtime_root: str | None
    runtime_pid: int | None
    terminal_backend: str | None
    pane_id: str | None
    pane_title_marker: str | None
    pane_state: str | None
    tmux_socket_name: str | None
    tmux_socket_path: str | None
    session_file: str | None
    session_id: str | None


def load_provider_session(binding, workspace_path: Path, agent_name: str):
    instance = named_agent_instance(agent_name, primary_agent=str(getattr(binding, "provider", "") or ""))
    try:
        return binding.load_session(workspace_path, instance)
    except Exception:
        return None


def ensure_provider_pane(session) -> tuple[bool, str]:
    ensure = getattr(session, 'ensure_pane', None)
    if not callable(ensure):
        return False, 'ensure_pane not supported'
    try:
        return ensure()
    except Exception as exc:
        return False, str(exc)


def build_provider_runtime_facts(
    session,
    *,
    binding,
    provider: str,
    pane_id_override: str | None = None,
) -> ProviderRuntimeFacts:
    pane_id = str(pane_id_override or getattr(session, 'pane_id', '') or '').strip() or None
    return ProviderRuntimeFacts(
        runtime_ref=session_runtime_ref(session, pane_id_override=pane_id),
        session_ref=session_ref(
            session,
            session_id_attr=binding.session_id_attr,
            session_path_attr=binding.session_path_attr,
        ),
        runtime_root=session_runtime_root(session),
        runtime_pid=session_runtime_pid(session, provider=provider),
        terminal_backend=session_terminal(session),
        pane_id=pane_id,
        pane_title_marker=session_pane_title_marker(session),
        pane_state='alive' if pane_id else None,
        tmux_socket_name=session_tmux_socket_name(session),
        tmux_socket_path=session_tmux_socket_path(session),
        session_file=session_file(session),
        session_id=session_id(session, session_id_attr=binding.session_id_attr),
    )


__all__ = [
    'ProviderRuntimeFacts',
    'build_provider_runtime_facts',
    'ensure_provider_pane',
    'load_provider_session',
]
