from __future__ import annotations

from storage.paths import PathLayout
from terminal_runtime import TmuxBackend

from ccbd.system import utc_now

from .backend import build_backend, session_root_pane, session_window_target, window_root_pane
from .controller_state import ProjectNamespaceControllerState, ProjectNamespaceControllerStateMixin
from .destroy import destroy_project_namespace
from .ensure import ensure_project_namespace
from .models import ProjectNamespace
from .reflow import reflow_project_workspace
from .records import namespace_from_state
from ..project_namespace_state import ProjectNamespaceEventStore, ProjectNamespaceStateStore


class ProjectNamespaceController(ProjectNamespaceControllerStateMixin):
    def __init__(
        self,
        layout: PathLayout,
        project_id: str,
        *,
        clock=utc_now,
        backend_factory=None,
        state_store: ProjectNamespaceStateStore | None = None,
        event_store: ProjectNamespaceEventStore | None = None,
        layout_version: int = 3,
    ) -> None:
        resolved_project_id = str(project_id or '').strip()
        if not resolved_project_id:
            raise ValueError('project_id cannot be empty')
        resolved_layout_version = int(layout_version)
        if resolved_layout_version <= 0:
            raise ValueError('layout_version must be positive')
        self._runtime_state = ProjectNamespaceControllerState(
            layout=layout,
            project_id=resolved_project_id,
            clock=clock,
            backend_factory=backend_factory or TmuxBackend,
            state_store=state_store or ProjectNamespaceStateStore(layout),
            event_store=event_store or ProjectNamespaceEventStore(layout),
            layout_version=resolved_layout_version,
        )

    def load(self) -> ProjectNamespace | None:
        state = self._state_store.load()
        if state is None:
            return None
        return namespace_from_state(state)

    def ensure(
        self,
        *,
        layout_signature: str | None = None,
        force_recreate: bool = False,
        recreate_reason: str | None = None,
        session_probe_timeout_s: float | None = None,
        terminal_size: tuple[int, int] | None = None,
    ) -> ProjectNamespace:
        return ensure_project_namespace(
            self,
            layout_signature=layout_signature,
            force_recreate=force_recreate,
            recreate_reason=recreate_reason,
            session_probe_timeout_s=session_probe_timeout_s,
            terminal_size=terminal_size,
        )

    def destroy(self, *, reason: str, force: bool = False):
        del force
        return destroy_project_namespace(self, reason=reason)

    def reflow_workspace(
        self,
        *,
        layout_signature: str | None = None,
        reason: str | None = None,
        session_probe_timeout_s: float | None = None,
    ) -> ProjectNamespace:
        return reflow_project_workspace(
            self,
            layout_signature=layout_signature,
            reason=reason,
            session_probe_timeout_s=session_probe_timeout_s,
        )

    def root_pane_id(
        self,
        namespace: ProjectNamespace | None = None,
        *,
        timeout_s: float | None = None,
    ) -> str:
        current = namespace or self.load()
        if current is None:
            raise RuntimeError('project namespace is not available')
        backend = build_backend(self._backend_factory, socket_path=current.tmux_socket_path)
        workspace_window_name = str(current.workspace_window_name or '').strip()
        if workspace_window_name:
            return window_root_pane(
                backend,
                target_window=session_window_target(current.tmux_session_name, workspace_window_name),
                timeout_s=timeout_s,
            )
        return session_root_pane(backend, current.tmux_session_name, timeout_s=timeout_s)


__all__ = ['ProjectNamespaceController']
