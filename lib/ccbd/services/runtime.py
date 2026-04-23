from __future__ import annotations

from agents.models import AgentRuntime, RuntimeBindingSource
from agents.store import AgentRestoreStore
from ccbd.system import utc_now
from provider_core.registry import build_default_session_binding_map
from storage.paths import PathLayout

from .registry import AgentRegistry
from .runtime_runtime.attach import attach_runtime as attach_runtime_impl
from .runtime_runtime.common import ACTIVE_RUNTIME_STATES
from .runtime_runtime.refresh import refresh_provider_binding as refresh_provider_binding_impl
from .runtime_runtime.restore import ensure_runtime_ready as ensure_runtime_ready_impl
from .runtime_runtime.restore import restore_runtime as restore_runtime_impl

_ACTIVE_STATES = ACTIVE_RUNTIME_STATES


class RuntimeService:
    def __init__(
        self,
        layout: PathLayout,
        registry: AgentRegistry,
        project_id: str,
        restore_store: AgentRestoreStore | None = None,
        session_bindings=None,
        *,
        clock=utc_now,
    ) -> None:
        self._layout = layout
        self._registry = registry
        self._project_id = project_id
        self._restore_store = restore_store or AgentRestoreStore(layout)
        self._session_bindings = session_bindings or build_default_session_binding_map(include_optional=True)
        self._clock = clock

    def attach(
        self,
        *,
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
        return attach_runtime_impl(
            registry=self._registry,
            project_id=self._project_id,
            clock=self._clock,
            agent_name=agent_name,
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

    def restore(self, agent_name: str):
        return restore_runtime_impl(
            layout=self._layout,
            registry=self._registry,
            restore_store=self._restore_store,
            attach_runtime_fn=self.attach,
            clock=self._clock,
            agent_name=agent_name,
        )

    def ensure_ready(self, agent_name: str) -> AgentRuntime:
        return ensure_runtime_ready_impl(
            layout=self._layout,
            registry=self._registry,
            restore_store=self._restore_store,
            attach_runtime_fn=self.attach,
            restore_runtime_fn=self.restore,
            clock=self._clock,
            agent_name=agent_name,
        )

    def refresh_provider_binding(self, agent_name: str, *, recover: bool = False) -> AgentRuntime | None:
        return refresh_provider_binding_impl(
            layout=self._layout,
            registry=self._registry,
            session_bindings=self._session_bindings,
            attach_runtime_fn=self.attach,
            agent_name=agent_name,
            recover=recover,
        )


__all__ = ['RuntimeService']
