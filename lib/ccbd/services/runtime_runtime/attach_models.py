from __future__ import annotations

from dataclasses import dataclass

from agents.models import RuntimeBindingSource


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
    slot_key: str | None
    window_id: str | None
    workspace_epoch: int | None
    lifecycle_state: str | None
    binding_generation: int
    runtime_generation: int
    daemon_generation: int | None
    authority_epoch_changed: bool
    managed_by: str
    binding_source: RuntimeBindingSource


__all__ = ['AttachRuntimeValues']
