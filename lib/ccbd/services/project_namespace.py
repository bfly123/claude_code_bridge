from __future__ import annotations

from dataclasses import dataclass

from ccbd.system import utc_now
from cli.services.tmux_ui import apply_project_tmux_ui
from storage.paths import PathLayout
from terminal_runtime import TmuxBackend
from terminal_runtime.tmux_identity import apply_ccb_pane_identity

from .project_namespace_state import (
    ProjectNamespaceEvent,
    ProjectNamespaceEventStore,
    ProjectNamespaceState,
    ProjectNamespaceStateStore,
    next_namespace_epoch,
)


@dataclass(frozen=True)
class ProjectNamespace:
    project_id: str
    namespace_epoch: int
    tmux_socket_path: str
    tmux_session_name: str
    layout_version: int
    layout_signature: str | None
    ui_attachable: bool
    created_this_call: bool = False

    @classmethod
    def from_state(cls, state: ProjectNamespaceState) -> ProjectNamespace:
        return cls(
            project_id=state.project_id,
            namespace_epoch=state.namespace_epoch,
            tmux_socket_path=state.tmux_socket_path,
            tmux_session_name=state.tmux_session_name,
            layout_version=state.layout_version,
            layout_signature=state.layout_signature,
            ui_attachable=state.ui_attachable,
            created_this_call=False,
        )


@dataclass(frozen=True)
class ProjectNamespaceDestroySummary:
    project_id: str
    namespace_epoch: int | None
    tmux_socket_path: str
    tmux_session_name: str
    destroyed: bool
    reason: str


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
        return ProjectNamespace.from_state(state)

    def ensure(
        self,
        *,
        layout_signature: str | None = None,
        force_recreate: bool = False,
        recreate_reason: str | None = None,
    ) -> ProjectNamespace:
        self._layout.ccbd_dir.mkdir(parents=True, exist_ok=True)
        desired_socket_path = str(self._layout.ccbd_tmux_socket_path)
        desired_session_name = self._layout.ccbd_tmux_session_name
        desired_layout_signature = str(layout_signature or '').strip() or None
        current = self._state_store.load()
        backend = self._build_backend(desired_socket_path)
        session_alive = self._session_alive(backend, desired_session_name)
        recreate_cause: str | None = None

        if force_recreate and session_alive:
            self._kill_server(backend)
            backend = self._build_backend(desired_socket_path)
            session_alive = False
            recreate_cause = str(recreate_reason or '').strip() or 'forced_recreate'

        if (
            current is not None
            and session_alive
            and int(current.layout_version) != self._layout_version
        ):
            self._kill_server(backend)
            backend = self._build_backend(desired_socket_path)
            session_alive = False
            recreate_cause = 'layout_version_changed'

        if (
            current is not None
            and session_alive
            and desired_layout_signature is not None
            and str(current.layout_signature or '').strip() != desired_layout_signature
        ):
            self._kill_server(backend)
            backend = self._build_backend(desired_socket_path)
            session_alive = False
            recreate_cause = 'layout_signature_changed'

        if session_alive and current is not None:
            root_pane = self._session_root_pane(backend, desired_session_name)
            apply_ccb_pane_identity(
                backend,
                root_pane,
                title='cmd',
                agent_label='cmd',
                project_id=self._project_id,
                is_cmd=True,
                slot_key='cmd',
                namespace_epoch=current.namespace_epoch,
                managed_by='ccbd',
            )
            apply_project_tmux_ui(
                tmux_socket_path=desired_socket_path,
                tmux_session_name=desired_session_name,
                backend=backend,
            )
            state = ProjectNamespaceState(
                project_id=self._project_id,
                namespace_epoch=current.namespace_epoch,
                tmux_socket_path=desired_socket_path,
                tmux_session_name=desired_session_name,
                layout_version=self._layout_version,
                layout_signature=desired_layout_signature or current.layout_signature,
                ui_attachable=True,
                last_started_at=current.last_started_at,
                last_destroyed_at=current.last_destroyed_at,
                last_destroy_reason=current.last_destroy_reason,
            )
            self._state_store.save(state)
            return ProjectNamespace.from_state(state)

        occurred_at = self._clock()
        epoch = next_namespace_epoch(current)
        self._prepare_server(backend)
        if not session_alive:
            self._create_session(backend, desired_session_name)
        root_pane = self._session_root_pane(backend, desired_session_name)
        apply_ccb_pane_identity(
            backend,
            root_pane,
            title='cmd',
            agent_label='cmd',
            project_id=self._project_id,
            is_cmd=True,
            slot_key='cmd',
            namespace_epoch=epoch,
            managed_by='ccbd',
        )
        apply_project_tmux_ui(
            tmux_socket_path=desired_socket_path,
            tmux_session_name=desired_session_name,
            backend=backend,
        )
        state = ProjectNamespaceState(
            project_id=self._project_id,
            namespace_epoch=epoch,
            tmux_socket_path=desired_socket_path,
            tmux_session_name=desired_session_name,
            layout_version=self._layout_version,
            layout_signature=desired_layout_signature,
            ui_attachable=True,
            last_started_at=occurred_at,
            last_destroyed_at=current.last_destroyed_at if current is not None else None,
            last_destroy_reason=current.last_destroy_reason if current is not None else None,
        )
        self._state_store.save(state)
        self._event_store.append(
            ProjectNamespaceEvent(
                event_kind='namespace_created',
                project_id=self._project_id,
                occurred_at=occurred_at,
                namespace_epoch=epoch,
                tmux_socket_path=desired_socket_path,
                tmux_session_name=desired_session_name,
                details={
                    'recreated': bool(current is not None),
                    'reason': recreate_cause or ('missing_session' if current is not None else 'initial_create'),
                },
            )
        )
        return ProjectNamespace(
            project_id=state.project_id,
            namespace_epoch=state.namespace_epoch,
            tmux_socket_path=state.tmux_socket_path,
            tmux_session_name=state.tmux_session_name,
            layout_version=state.layout_version,
            layout_signature=state.layout_signature,
            ui_attachable=state.ui_attachable,
            created_this_call=True,
        )

    def destroy(self, *, reason: str, force: bool = False) -> ProjectNamespaceDestroySummary:
        del force
        self._layout.ccbd_dir.mkdir(parents=True, exist_ok=True)
        state = self._state_store.load()
        occurred_at = self._clock()
        tmux_socket_path = str(state.tmux_socket_path) if state is not None else str(self._layout.ccbd_tmux_socket_path)
        tmux_session_name = str(state.tmux_session_name) if state is not None else self._layout.ccbd_tmux_session_name
        backend = self._build_backend(tmux_socket_path)
        destroyed = self._kill_server(backend)
        next_state = (
            state.with_destroyed(occurred_at=occurred_at, reason=reason)
            if state is not None
            else ProjectNamespaceState(
                project_id=self._project_id,
                namespace_epoch=1,
                tmux_socket_path=tmux_socket_path,
                tmux_session_name=tmux_session_name,
                layout_version=self._layout_version,
                ui_attachable=False,
                last_started_at=None,
                last_destroyed_at=occurred_at,
                last_destroy_reason=str(reason or '').strip() or 'destroyed',
            )
        )
        self._state_store.save(next_state)
        self._event_store.append(
            ProjectNamespaceEvent(
                event_kind='namespace_destroyed',
                project_id=self._project_id,
                occurred_at=occurred_at,
                namespace_epoch=next_state.namespace_epoch,
                tmux_socket_path=tmux_socket_path,
                tmux_session_name=tmux_session_name,
                details={'destroyed': destroyed, 'reason': str(reason or '').strip() or 'destroyed'},
            )
        )
        return ProjectNamespaceDestroySummary(
            project_id=self._project_id,
            namespace_epoch=next_state.namespace_epoch,
            tmux_socket_path=tmux_socket_path,
            tmux_session_name=tmux_session_name,
            destroyed=destroyed,
            reason=str(reason or '').strip() or 'destroyed',
        )

    def root_pane_id(self, namespace: ProjectNamespace | None = None) -> str:
        current = namespace or self.load()
        if current is None:
            raise RuntimeError('project namespace is not available')
        backend = self._build_backend(current.tmux_socket_path)
        return self._session_root_pane(backend, current.tmux_session_name)

    def _build_backend(self, socket_path: str):
        try:
            return self._backend_factory(socket_path=socket_path)
        except TypeError:
            return self._backend_factory()

    @staticmethod
    def _prepare_server(backend) -> None:
        backend._tmux_run(['start-server'], check=False, capture=True)  # type: ignore[attr-defined]
        backend._tmux_run(['set-option', '-g', 'destroy-unattached', 'off'], check=False, capture=True)  # type: ignore[attr-defined]

    def _create_session(self, backend, session_name: str) -> None:
        backend._tmux_run(
            [
                'new-session',
                '-d',
                '-x',
                '160',
                '-y',
                '48',
                '-s',
                session_name,
                '-c',
                str(self._layout.project_root),
                'sh',
                '-lc',
                'while :; do sleep 3600; done',
            ],
            check=True,
        )  # type: ignore[attr-defined]

    @staticmethod
    def _session_alive(backend, session_name: str) -> bool:
        checker = getattr(backend, 'is_alive', None)
        if not callable(checker):
            return False
        try:
            return bool(checker(session_name))
        except Exception:
            return False

    @staticmethod
    def _session_root_pane(backend, session_name: str) -> str:
        result = backend._tmux_run(  # type: ignore[attr-defined]
            ['list-panes', '-t', session_name, '-F', '#{pane_id}'],
            capture=True,
            check=True,
        )
        pane_id = ((result.stdout or '').splitlines() or [''])[0].strip()
        if not pane_id.startswith('%'):
            raise RuntimeError(f'failed to resolve root pane for tmux session {session_name!r}')
        return pane_id

    @staticmethod
    def _kill_server(backend) -> bool:
        try:
            backend._tmux_run(['kill-server'], check=False, capture=True)  # type: ignore[attr-defined]
            return True
        except Exception:
            return False


__all__ = ['ProjectNamespace', 'ProjectNamespaceController', 'ProjectNamespaceDestroySummary']
