from __future__ import annotations

from dataclasses import dataclass
from dataclasses import replace

from agents.models import AgentRuntime, RuntimeBindingSource
from agents.runtime_binding import merge_runtime_binding, runtime_binding_from_runtime

from ..runtime_attach import (
    binding_source_for_attach,
    normalized_text,
    pane_id_from_runtime_ref,
    resolve_session_fields,
    state_for_attach,
    terminal_backend_from_runtime_ref,
)
from .common import ACTIVE_RUNTIME_STATES


@dataclass(frozen=True)
class AttachRuntimeValues:
    backend_type: str
    runtime_ref: str | None
    session_ref: str | None
    workspace_path: str
    state: object
    health: str
    provider: str
    runtime_root: str | None
    runtime_pid: int | None
    terminal_backend: str | None
    pane_id: str | None
    active_pane_id: str | None
    pane_title_marker: str | None
    pane_state: str | None
    tmux_socket_name: str | None
    tmux_socket_path: str | None
    session_file: str | None
    session_id: str | None
    lifecycle_state: str | None
    binding_generation: int
    managed_by: str
    binding_source: RuntimeBindingSource


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
    terminal_backend: str | None = None,
    pane_id: str | None = None,
    active_pane_id: str | None = None,
    pane_title_marker: str | None = None,
    pane_state: str | None = None,
    tmux_socket_name: str | None = None,
    tmux_socket_path: str | None = None,
    session_file: str | None = None,
    session_id: str | None = None,
    lifecycle_state: str | None = None,
    managed_by: str | None = None,
    binding_source: str | RuntimeBindingSource | None = None,
) -> AgentRuntime:
    spec = registry.spec_for(agent_name)
    existing = registry.get(agent_name)
    timestamp = clock()
    values = _resolve_attach_runtime_values(
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
        terminal_backend=terminal_backend,
        pane_id=pane_id,
        active_pane_id=active_pane_id,
        pane_title_marker=pane_title_marker,
        pane_state=pane_state,
        tmux_socket_name=tmux_socket_name,
        tmux_socket_path=tmux_socket_path,
        session_file=session_file,
        session_id=session_id,
        lifecycle_state=lifecycle_state,
        managed_by=managed_by,
        binding_source=binding_source,
    )

    if _should_update_existing(existing):
        updated = _updated_runtime(
            existing,
            values=values,
            timestamp=timestamp,
            project_id=project_id,
        )
        return registry.upsert(updated)

    runtime = _new_runtime(
        spec_name=spec.name,
        existing=existing,
        values=values,
        timestamp=timestamp,
        project_id=project_id,
    )
    return registry.upsert(runtime)


def _resolve_attach_runtime_values(
    *,
    existing,
    spec,
    workspace_path: str,
    backend_type: str,
    pid: int | None,
    runtime_ref: str | None,
    session_ref: str | None,
    health: str | None,
    provider: str | None,
    runtime_root: str | None,
    runtime_pid: int | None,
    terminal_backend: str | None,
    pane_id: str | None,
    active_pane_id: str | None,
    pane_title_marker: str | None,
    pane_state: str | None,
    tmux_socket_name: str | None,
    tmux_socket_path: str | None,
    session_file: str | None,
    session_id: str | None,
    lifecycle_state: str | None,
    managed_by: str | None,
    binding_source: str | RuntimeBindingSource | None,
) -> AttachRuntimeValues:
    merged_binding = merge_runtime_binding(
        runtime_binding_from_runtime(existing),
        runtime_ref=runtime_ref,
        session_ref=session_ref,
        workspace_path=workspace_path,
    )
    session_file_value, session_id_value, session_ref_value = resolve_session_fields(
        existing,
        session_ref=merged_binding.session_ref,
        session_file=session_file,
        session_id=session_id,
        session_ref_explicit=session_ref is not None,
        session_file_explicit=session_file is not None,
        session_id_explicit=session_id is not None,
    )
    runtime_ref_value = merged_binding.runtime_ref
    next_health = health or (existing.health if existing is not None else 'healthy')
    next_state = state_for_attach(existing.state if existing is not None else None, next_health)
    pane_id_value = _preferred_pane_id(existing, pane_id=pane_id, runtime_ref_value=runtime_ref_value)
    return AttachRuntimeValues(
        backend_type=backend_type,
        runtime_ref=runtime_ref_value,
        session_ref=session_ref_value,
        workspace_path=merged_binding.workspace_path,
        state=next_state,
        health=next_health,
        provider=_next_provider(existing, spec, provider),
        runtime_root=_preferred_text(existing, 'runtime_root', runtime_root),
        runtime_pid=_next_runtime_pid(existing, runtime_pid=runtime_pid, pid=pid),
        terminal_backend=_preferred_terminal_backend(existing, terminal_backend=terminal_backend, runtime_ref_value=runtime_ref_value),
        pane_id=pane_id_value,
        active_pane_id=_preferred_active_pane_id(existing, active_pane_id=active_pane_id, pane_id_value=pane_id_value),
        pane_title_marker=_preferred_text(existing, 'pane_title_marker', pane_title_marker),
        pane_state=_preferred_text(existing, 'pane_state', pane_state),
        tmux_socket_name=_preferred_text(existing, 'tmux_socket_name', tmux_socket_name),
        tmux_socket_path=_preferred_text(existing, 'tmux_socket_path', tmux_socket_path),
        session_file=session_file_value,
        session_id=session_id_value,
        lifecycle_state=_next_lifecycle_state(existing, lifecycle_state=lifecycle_state, next_state=next_state),
        binding_generation=(existing.binding_generation + 1) if existing is not None else 1,
        managed_by=_preferred_text(existing, 'managed_by', managed_by, default='ccbd') or 'ccbd',
        binding_source=binding_source_for_attach(existing, explicit=binding_source),
    )


def _next_provider(existing, spec, provider: str | None) -> str:
    current = existing.provider if existing is not None else spec.provider
    return str(provider or current or spec.provider).strip() or spec.provider


def _preferred_text(existing, field_name: str, explicit_value: str | None, *, default: str | None = None) -> str | None:
    normalized = normalized_text(explicit_value)
    if normalized is not None:
        return normalized
    if existing is not None:
        return getattr(existing, field_name)
    return default


def _preferred_terminal_backend(existing, *, terminal_backend: str | None, runtime_ref_value: str | None) -> str | None:
    return (
        normalized_text(terminal_backend)
        or terminal_backend_from_runtime_ref(runtime_ref_value)
        or (existing.terminal_backend if existing is not None else None)
    )


def _preferred_pane_id(existing, *, pane_id: str | None, runtime_ref_value: str | None) -> str | None:
    return (
        normalized_text(pane_id)
        or pane_id_from_runtime_ref(runtime_ref_value)
        or (existing.pane_id if existing is not None else None)
    )


def _preferred_active_pane_id(existing, *, active_pane_id: str | None, pane_id_value: str | None) -> str | None:
    return (
        normalized_text(active_pane_id)
        or pane_id_value
        or (existing.active_pane_id if existing is not None else None)
    )


def _next_runtime_pid(existing, *, runtime_pid: int | None, pid: int | None) -> int | None:
    if runtime_pid is not None:
        return runtime_pid
    if pid is not None:
        return pid
    return existing.runtime_pid if existing is not None else None


def _next_lifecycle_state(existing, *, lifecycle_state: str | None, next_state) -> str | None:
    return (
        normalized_text(lifecycle_state)
        or (existing.lifecycle_state if existing is not None else None)
        or next_state.value
    )


def _should_update_existing(existing) -> bool:
    return existing is not None and existing.state in ACTIVE_RUNTIME_STATES


def _updated_runtime(existing, *, values: AttachRuntimeValues, timestamp: str, project_id: str) -> AgentRuntime:
    return replace(
        existing,
        state=values.state,
        last_seen_at=timestamp,
        pid=values.runtime_pid,
        workspace_path=values.workspace_path,
        backend_type=values.backend_type or existing.backend_type,
        runtime_ref=values.runtime_ref,
        session_ref=values.session_ref,
        project_id=existing.project_id or project_id,
        health=values.health,
        provider=values.provider,
        runtime_root=values.runtime_root,
        runtime_pid=values.runtime_pid,
        terminal_backend=values.terminal_backend,
        pane_id=values.pane_id,
        active_pane_id=values.active_pane_id,
        pane_title_marker=values.pane_title_marker,
        pane_state=values.pane_state,
        tmux_socket_name=values.tmux_socket_name,
        tmux_socket_path=values.tmux_socket_path,
        session_file=values.session_file,
        session_id=values.session_id,
        lifecycle_state=values.lifecycle_state,
        binding_generation=values.binding_generation,
        managed_by=values.managed_by,
        binding_source=values.binding_source,
    )


def _new_runtime(
    *,
    spec_name: str,
    existing,
    values: AttachRuntimeValues,
    timestamp: str,
    project_id: str,
) -> AgentRuntime:
    return AgentRuntime(
        agent_name=spec_name,
        state=values.state,
        pid=values.runtime_pid,
        started_at=existing.started_at if existing and existing.started_at else timestamp,
        last_seen_at=timestamp,
        runtime_ref=values.runtime_ref,
        session_ref=values.session_ref,
        workspace_path=values.workspace_path,
        project_id=existing.project_id if existing else project_id,
        backend_type=values.backend_type,
        queue_depth=existing.queue_depth if existing else 0,
        socket_path=existing.socket_path if existing else None,
        health=values.health,
        provider=values.provider,
        runtime_root=values.runtime_root,
        runtime_pid=values.runtime_pid,
        terminal_backend=values.terminal_backend,
        pane_id=values.pane_id,
        active_pane_id=values.active_pane_id,
        pane_title_marker=values.pane_title_marker,
        pane_state=values.pane_state,
        tmux_socket_name=values.tmux_socket_name,
        tmux_socket_path=values.tmux_socket_path,
        session_file=values.session_file,
        session_id=values.session_id,
        lifecycle_state=values.lifecycle_state,
        binding_generation=values.binding_generation,
        managed_by=values.managed_by,
        binding_source=values.binding_source,
    )
