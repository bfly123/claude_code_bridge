from __future__ import annotations

from dataclasses import dataclass

from .common import binding_pane_id, matching_project_namespace_record


@dataclass(frozen=True)
class BindingValidationContext:
    tmux_socket_path: str
    tmux_session_name: str | None
    workspace_window_id: str | None
    agent_name: str
    project_id: str
    tmux_backend_factory: object
    inspect_project_namespace_pane_fn: object
    same_tmux_socket_path_fn: object


def binding_runtime_ref(binding) -> str:
    return str(getattr(binding, 'runtime_ref', None) or '').strip()


def binding_pane_state(binding) -> str:
    return str(getattr(binding, 'pane_state', None) or '').strip().lower()


def is_tmux_binding(binding) -> bool:
    return binding_runtime_ref(binding).startswith('tmux:')


def build_binding_validation_context(
    *,
    tmux_socket_path: str,
    tmux_session_name: str | None,
    workspace_window_id: str | None,
    agent_name: str,
    project_id: str,
    tmux_backend_factory,
    inspect_project_namespace_pane_fn,
    same_tmux_socket_path_fn,
) -> BindingValidationContext:
    return BindingValidationContext(
        tmux_socket_path=tmux_socket_path,
        tmux_session_name=tmux_session_name,
        workspace_window_id=workspace_window_id,
        agent_name=agent_name,
        project_id=project_id,
        tmux_backend_factory=tmux_backend_factory,
        inspect_project_namespace_pane_fn=inspect_project_namespace_pane_fn,
        same_tmux_socket_path_fn=same_tmux_socket_path_fn,
    )


def matching_namespace_binding(binding, *, context: BindingValidationContext):
    return matching_project_namespace_record(
        binding=binding,
        tmux_socket_path=context.tmux_socket_path,
        tmux_session_name=context.tmux_session_name,
        workspace_window_id=context.workspace_window_id,
        agent_name=context.agent_name,
        project_id=context.project_id,
        tmux_backend_factory=context.tmux_backend_factory,
        inspect_project_namespace_pane_fn=context.inspect_project_namespace_pane_fn,
    )


def binding_matches_project_socket(binding, *, context: BindingValidationContext) -> bool:
    return context.same_tmux_socket_path_fn(
        getattr(binding, 'tmux_socket_path', None),
        context.tmux_socket_path,
    )


def binding_has_live_namespace_record(binding, *, context: BindingValidationContext) -> bool:
    return matching_namespace_binding(binding=binding, context=context) is not None


def is_live_tmux_binding(binding) -> bool:
    return binding is not None and is_tmux_binding(binding) and binding_pane_state(binding) == 'alive'


def has_reusable_tmux_pane(binding) -> bool:
    return binding is not None and is_tmux_binding(binding) and binding_pane_id(binding) is not None


def has_acceptable_provider_runtime_identity(binding) -> bool:
    state = str(getattr(binding, 'provider_identity_state', None) or '').strip().lower()
    if not state:
        return True
    return state == 'match'


def has_no_provider_runtime_identity_mismatch(binding) -> bool:
    state = str(getattr(binding, 'provider_identity_state', None) or '').strip().lower()
    return state != 'mismatch'


def declares_current_project_socket(binding_socket_path: str | None, *, context: BindingValidationContext) -> bool:
    return context.same_tmux_socket_path_fn(binding_socket_path, context.tmux_socket_path)


def has_project_tmux_session_name(context: BindingValidationContext) -> bool:
    return bool(str(context.tmux_session_name or '').strip())


__all__ = [
    'BindingValidationContext',
    'binding_has_live_namespace_record',
    'binding_matches_project_socket',
    'binding_pane_state',
    'build_binding_validation_context',
    'declares_current_project_socket',
    'has_acceptable_provider_runtime_identity',
    'has_no_provider_runtime_identity_mismatch',
    'has_project_tmux_session_name',
    'has_reusable_tmux_pane',
    'is_live_tmux_binding',
]
