from __future__ import annotations

from cli.services.tmux_ui import apply_project_tmux_ui
from terminal_runtime.tmux_identity import apply_ccb_pane_identity

from .backend import build_backend, create_session, kill_server, prepare_server, session_alive, session_root_pane
from .models import ProjectNamespace
from .records import build_active_state, build_created_event, namespace_from_state, normalized_layout_signature
from ..project_namespace_state import next_namespace_epoch


def ensure_project_namespace(
    controller,
    *,
    layout_signature: str | None = None,
    force_recreate: bool = False,
    recreate_reason: str | None = None,
) -> ProjectNamespace:
    controller._layout.ccbd_dir.mkdir(parents=True, exist_ok=True)
    desired_socket_path = str(controller._layout.ccbd_tmux_socket_path)
    desired_session_name = controller._layout.ccbd_tmux_session_name
    desired_layout_signature = normalized_layout_signature(layout_signature)
    current = controller._state_store.load()
    backend = build_backend(controller._backend_factory, socket_path=desired_socket_path)
    session_is_alive = session_alive(backend, desired_session_name)
    recreate_cause: str | None = None

    if force_recreate and session_is_alive:
        kill_server(backend)
        backend = build_backend(controller._backend_factory, socket_path=desired_socket_path)
        session_is_alive = False
        recreate_cause = str(recreate_reason or '').strip() or 'forced_recreate'

    recreate_cause, backend, session_is_alive = _recreate_for_layout_change(
        controller,
        current=current,
        backend=backend,
        session_is_alive=session_is_alive,
        desired_socket_path=desired_socket_path,
        desired_layout_signature=desired_layout_signature,
        recreate_cause=recreate_cause,
    )

    if session_is_alive and current is not None:
        state = _refresh_existing_namespace(
            controller,
            current=current,
            backend=backend,
            desired_socket_path=desired_socket_path,
            desired_session_name=desired_session_name,
            desired_layout_signature=desired_layout_signature,
        )
        controller._state_store.save(state)
        return namespace_from_state(state)

    occurred_at = controller._clock()
    epoch = next_namespace_epoch(current)
    prepare_server(backend)
    if not session_is_alive:
        create_session(
            backend,
            session_name=desired_session_name,
            project_root=controller._layout.project_root,
        )
    root_pane = session_root_pane(backend, desired_session_name)
    _apply_namespace_identity(
        controller,
        backend=backend,
        pane_id=root_pane,
        namespace_epoch=epoch,
        tmux_socket_path=desired_socket_path,
        tmux_session_name=desired_session_name,
    )
    state = build_active_state(
        project_id=controller._project_id,
        current=current,
        namespace_epoch=epoch,
        tmux_socket_path=desired_socket_path,
        tmux_session_name=desired_session_name,
        layout_version=controller._layout_version,
        layout_signature=desired_layout_signature,
        ui_attachable=True,
        last_started_at=occurred_at,
    )
    controller._state_store.save(state)
    controller._event_store.append(
        build_created_event(
            project_id=controller._project_id,
            occurred_at=occurred_at,
            namespace_epoch=epoch,
            tmux_socket_path=desired_socket_path,
            tmux_session_name=desired_session_name,
            recreated=bool(current is not None),
            reason=recreate_cause or ('missing_session' if current is not None else 'initial_create'),
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


def _recreate_for_layout_change(
    controller,
    *,
    current,
    backend,
    session_is_alive: bool,
    desired_socket_path: str,
    desired_layout_signature: str | None,
    recreate_cause: str | None,
):
    if current is not None and session_is_alive and int(current.layout_version) != controller._layout_version:
        kill_server(backend)
        backend = build_backend(controller._backend_factory, socket_path=desired_socket_path)
        session_is_alive = False
        recreate_cause = 'layout_version_changed'

    if (
        current is not None
        and session_is_alive
        and desired_layout_signature is not None
        and str(current.layout_signature or '').strip() != desired_layout_signature
    ):
        kill_server(backend)
        backend = build_backend(controller._backend_factory, socket_path=desired_socket_path)
        session_is_alive = False
        recreate_cause = 'layout_signature_changed'

    return recreate_cause, backend, session_is_alive


def _refresh_existing_namespace(
    controller,
    *,
    current,
    backend,
    desired_socket_path: str,
    desired_session_name: str,
    desired_layout_signature: str | None,
):
    root_pane = session_root_pane(backend, desired_session_name)
    _apply_namespace_identity(
        controller,
        backend=backend,
        pane_id=root_pane,
        namespace_epoch=current.namespace_epoch,
        tmux_socket_path=desired_socket_path,
        tmux_session_name=desired_session_name,
    )
    return build_active_state(
        project_id=controller._project_id,
        current=current,
        namespace_epoch=current.namespace_epoch,
        tmux_socket_path=desired_socket_path,
        tmux_session_name=desired_session_name,
        layout_version=controller._layout_version,
        layout_signature=desired_layout_signature or current.layout_signature,
        ui_attachable=True,
        last_started_at=current.last_started_at,
    )


def _apply_namespace_identity(
    controller,
    *,
    backend,
    pane_id: str,
    namespace_epoch: int,
    tmux_socket_path: str,
    tmux_session_name: str,
) -> None:
    apply_ccb_pane_identity(
        backend,
        pane_id,
        title='cmd',
        agent_label='cmd',
        project_id=controller._project_id,
        is_cmd=True,
        slot_key='cmd',
        namespace_epoch=namespace_epoch,
        managed_by='ccbd',
    )
    apply_project_tmux_ui(
        tmux_socket_path=tmux_socket_path,
        tmux_session_name=tmux_session_name,
        backend=backend,
    )


__all__ = ['ensure_project_namespace']
