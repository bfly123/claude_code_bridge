from __future__ import annotations

from dataclasses import dataclass

from ccbd.models import CcbdStartupAgentResult


@dataclass(frozen=True)
class StartAgentExecution:
    agent_result: CcbdStartupAgentResult
    actions_taken: tuple[str, ...]
    socket_name: str | None
    runtime_pane_id: str | None
    project_socket_active_pane_id: str | None


@dataclass(frozen=True)
class RuntimeBindingState:
    binding: object | None
    agent_action: str
    actions_taken: tuple[str, ...]
    runtime_ref: str | None
    session_ref: str | None
    health: str
    lifecycle_state: str
    socket_name: str | None
    runtime_pane_id: str | None
    project_socket_active_pane_id: str | None


__all__ = ['RuntimeBindingState', 'StartAgentExecution']
