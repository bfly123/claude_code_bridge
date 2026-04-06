from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentBinding:
    runtime_ref: str | None
    session_ref: str | None
    provider: str | None = None
    runtime_root: str | None = None
    runtime_pid: int | None = None
    session_file: str | None = None
    session_id: str | None = None
    tmux_socket_name: str | None = None
    tmux_socket_path: str | None = None
    terminal: str | None = None
    pane_id: str | None = None
    active_pane_id: str | None = None
    pane_title_marker: str | None = None
    pane_state: str | None = None


def binding_status(runtime_ref: str | None, session_ref: str | None, workspace_path: str | None) -> str:
    if runtime_ref and session_ref and workspace_path:
        return 'bound'
    if runtime_ref or session_ref or workspace_path:
        return 'partial'
    return 'unbound'


__all__ = ['AgentBinding', 'binding_status']
