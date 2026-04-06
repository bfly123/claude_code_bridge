from __future__ import annotations

from storage.paths import PathLayout
from terminal_runtime import TmuxBackend

from ccbd.system import utc_now

from .backend import build_backend, session_root_pane
from .destroy import destroy_project_namespace
from .ensure import ensure_project_namespace
from .models import ProjectNamespace
from .records import namespace_from_state
from ..project_namespace_state import ProjectNamespaceEventStore, ProjectNamespaceStateStore


class ProjectNamespaceController:
    def __init__(
        self,
        layout: PathLayout,
        project_id: str,
        *,
        clock=utc_now,
        backend_factory=None,
        state_store: ProjectNamespaceStateStore | None = None,
        event_store: ProjectNamespaceEventStore | None = None,
        layout_version: int = 2,
    ) -> None:
        self._layout = layout
        self._project_id = str(project_id or '').strip()
        if not self._project_id:
            raise ValueError('project_id cannot be empty')
        self._clock = clock
        self._backend_factory = backend_factory or TmuxBackend
        self._state_store = state_store or ProjectNamespaceStateStore(layout)
        self._event_store = event_store or ProjectNamespaceEventStore(layout)
        self._layout_version = int(layout_version)
        if self._layout_version <= 0:
            raise ValueError('layout_version must be positive')

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
    ) -> ProjectNamespace:
        return ensure_project_namespace(
            self,
            layout_signature=layout_signature,
            force_recreate=force_recreate,
            recreate_reason=recreate_reason,
        )

    def destroy(self, *, reason: str, force: bool = False):
        del force
        return destroy_project_namespace(self, reason=reason)

    def root_pane_id(self, namespace: ProjectNamespace | None = None) -> str:
        current = namespace or self.load()
        if current is None:
            raise RuntimeError('project namespace is not available')
        backend = build_backend(self._backend_factory, socket_path=current.tmux_socket_path)
        return session_root_pane(backend, current.tmux_session_name)


__all__ = ['ProjectNamespaceController']
