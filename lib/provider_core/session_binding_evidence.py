from __future__ import annotations

import time

from provider_core.session_binding_evidence_runtime import (
    AgentBinding,
    binding_status,
    default_binding_adapter,
    inspect_session_pane,
    resolve_agent_binding as _resolve_agent_binding,
    session_file,
    session_id,
    session_job_id,
    session_job_owner_pid,
    session_pane_title_marker,
    session_ref,
    session_runtime_pid,
    session_runtime_ref,
    session_runtime_root,
    session_terminal,
    session_tmux_socket_name,
    session_tmux_socket_path,
)


def resolve_agent_binding(
    *,
    provider: str,
    agent_name: str,
    workspace_path,
    project_root=None,
    ensure_usable: bool = False,
    adapter_resolver=default_binding_adapter,
    sleep_fn=time.sleep,
):
    return _resolve_agent_binding(
        provider=provider,
        agent_name=agent_name,
        workspace_path=workspace_path,
        project_root=project_root,
        ensure_usable=ensure_usable,
        adapter_resolver=adapter_resolver,
        sleep_fn=sleep_fn,
    )


__all__ = [
    'AgentBinding',
    'binding_status',
    'default_binding_adapter',
    'inspect_session_pane',
    'resolve_agent_binding',
    'session_file',
    'session_id',
    'session_job_id',
    'session_job_owner_pid',
    'session_pane_title_marker',
    'session_ref',
    'session_runtime_pid',
    'session_runtime_ref',
    'session_runtime_root',
    'session_terminal',
    'session_tmux_socket_name',
    'session_tmux_socket_path',
]
