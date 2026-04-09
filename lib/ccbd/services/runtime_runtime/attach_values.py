from __future__ import annotations

from agents.models import RuntimeBindingSource
from agents.runtime_binding import merge_runtime_binding, runtime_binding_from_runtime

from ..runtime_attach import (
    binding_source_for_attach,
    normalized_text,
    pane_id_from_runtime_ref,
    resolve_session_fields,
    state_for_attach,
    terminal_backend_from_runtime_ref,
)
from .attach_models import AttachRuntimeValues


def resolve_attach_runtime_values(
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
    slot_key: str | None,
    window_id: str | None,
    workspace_epoch: int | None,
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
    pane_id_value = preferred_pane_id(existing, pane_id=pane_id, runtime_ref_value=runtime_ref_value)
    return AttachRuntimeValues(
        backend_type=backend_type,
        runtime_ref=runtime_ref_value,
        session_ref=session_ref_value,
        workspace_path=merged_binding.workspace_path,
        state=next_state,
        health=next_health,
        provider=next_provider(existing, spec, provider),
        runtime_root=preferred_text(existing, 'runtime_root', runtime_root),
        runtime_pid=next_runtime_pid(existing, runtime_pid=runtime_pid, pid=pid),
        terminal_backend=preferred_terminal_backend(existing, terminal_backend=terminal_backend, runtime_ref_value=runtime_ref_value),
        pane_id=pane_id_value,
        active_pane_id=preferred_active_pane_id(existing, active_pane_id=active_pane_id, pane_id_value=pane_id_value),
        pane_title_marker=preferred_text(existing, 'pane_title_marker', pane_title_marker),
        pane_state=preferred_text(existing, 'pane_state', pane_state),
        tmux_socket_name=preferred_text(existing, 'tmux_socket_name', tmux_socket_name),
        tmux_socket_path=preferred_text(existing, 'tmux_socket_path', tmux_socket_path),
        session_file=session_file_value,
        session_id=session_id_value,
        slot_key=preferred_slot_key(existing, spec_name=spec.name, slot_key=slot_key),
        window_id=preferred_text(existing, 'window_id', window_id),
        workspace_epoch=preferred_workspace_epoch(existing, workspace_epoch=workspace_epoch),
        lifecycle_state=next_lifecycle_state(existing, lifecycle_state=lifecycle_state, next_state=next_state),
        binding_generation=(existing.binding_generation + 1) if existing is not None else 1,
        managed_by=preferred_text(existing, 'managed_by', managed_by, default='ccbd') or 'ccbd',
        binding_source=binding_source_for_attach(existing, explicit=binding_source),
    )


def next_provider(existing, spec, provider: str | None) -> str:
    current = existing.provider if existing is not None else spec.provider
    return str(provider or current or spec.provider).strip() or spec.provider


def preferred_text(existing, field_name: str, explicit_value: str | None, *, default: str | None = None) -> str | None:
    normalized = normalized_text(explicit_value)
    if normalized is not None:
        return normalized
    if existing is not None:
        return getattr(existing, field_name)
    return default


def preferred_terminal_backend(existing, *, terminal_backend: str | None, runtime_ref_value: str | None) -> str | None:
    return (
        normalized_text(terminal_backend)
        or terminal_backend_from_runtime_ref(runtime_ref_value)
        or (existing.terminal_backend if existing is not None else None)
    )


def preferred_pane_id(existing, *, pane_id: str | None, runtime_ref_value: str | None) -> str | None:
    return (
        normalized_text(pane_id)
        or pane_id_from_runtime_ref(runtime_ref_value)
        or (existing.pane_id if existing is not None else None)
    )


def preferred_active_pane_id(existing, *, active_pane_id: str | None, pane_id_value: str | None) -> str | None:
    return (
        normalized_text(active_pane_id)
        or pane_id_value
        or (existing.active_pane_id if existing is not None else None)
    )


def preferred_slot_key(existing, *, spec_name: str, slot_key: str | None) -> str:
    return normalized_text(slot_key) or (existing.slot_key if existing is not None else None) or spec_name


def preferred_workspace_epoch(existing, *, workspace_epoch: int | None) -> int | None:
    if workspace_epoch is not None:
        return int(workspace_epoch)
    if existing is not None:
        return existing.workspace_epoch
    return None


def next_runtime_pid(existing, *, runtime_pid: int | None, pid: int | None) -> int | None:
    if runtime_pid is not None:
        return runtime_pid
    if pid is not None:
        return pid
    return existing.runtime_pid if existing is not None else None


def next_lifecycle_state(existing, *, lifecycle_state: str | None, next_state) -> str | None:
    return (
        normalized_text(lifecycle_state)
        or (existing.lifecycle_state if existing is not None else None)
        or next_state.value
    )


__all__ = ['resolve_attach_runtime_values']
