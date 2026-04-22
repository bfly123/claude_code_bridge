from __future__ import annotations

from agents.models import AgentRuntime, RuntimeBindingSource

from .attach_records import new_runtime, should_update_existing, updated_runtime
from .attach_values import resolve_attach_runtime_values


def attach_runtime(
    *,
    registry,
    project_id: str,
    clock,
    agent_name: str,
    workspace_path: str,
    backend_type: str,
    pid: int | None = None,
    runtime_ref: str | None = None,
    session_ref: str | None = None,
    health: str | None = None,
    provider: str | None = None,
    runtime_root: str | None = None,
    runtime_pid: int | None = None,
    job_id: str | None = None,
    job_owner_pid: int | None = None,
    terminal_backend: str | None = None,
    pane_id: str | None = None,
    active_pane_id: str | None = None,
    pane_title_marker: str | None = None,
    pane_state: str | None = None,
    tmux_socket_name: str | None = None,
    tmux_socket_path: str | None = None,
    session_file: str | None = None,
    session_id: str | None = None,
    slot_key: str | None = None,
    window_id: str | None = None,
    workspace_epoch: int | None = None,
    lifecycle_state: str | None = None,
    managed_by: str | None = None,
    binding_source: str | RuntimeBindingSource | None = None,
) -> AgentRuntime:
    spec = registry.spec_for(agent_name)
    existing = registry.get(agent_name)
    timestamp = clock()
    values = resolve_attach_runtime_values(
        existing=existing,
        spec=spec,
        workspace_path=workspace_path,
        backend_type=backend_type,
        pid=pid,
        runtime_ref=runtime_ref,
        session_ref=session_ref,
        health=health,
        provider=provider,
        runtime_root=runtime_root,
        runtime_pid=runtime_pid,
        job_id=job_id,
        job_owner_pid=job_owner_pid,
        terminal_backend=terminal_backend,
        pane_id=pane_id,
        active_pane_id=active_pane_id,
        pane_title_marker=pane_title_marker,
        pane_state=pane_state,
        tmux_socket_name=tmux_socket_name,
        tmux_socket_path=tmux_socket_path,
        session_file=session_file,
        session_id=session_id,
        slot_key=slot_key,
        window_id=window_id,
        workspace_epoch=workspace_epoch,
        lifecycle_state=lifecycle_state,
        managed_by=managed_by,
        binding_source=binding_source,
    )

    if should_update_existing(existing):
        updated = updated_runtime(
            existing,
            values=values,
            timestamp=timestamp,
            project_id=project_id,
        )
        return registry.upsert(updated)

    runtime = new_runtime(
        spec_name=spec.name,
        existing=existing,
        values=values,
        timestamp=timestamp,
        project_id=project_id,
    )
    return registry.upsert(runtime)
