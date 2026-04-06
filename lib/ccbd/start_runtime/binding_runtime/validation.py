from __future__ import annotations

from dataclasses import dataclass

from .common import binding_pane_id, matching_project_namespace_record
from .session_file import declared_binding_tmux_socket_path


@dataclass(frozen=True)
class _BindingValidationContext:
    tmux_socket_path: str
    tmux_session_name: str | None
    agent_name: str
    project_id: str
    tmux_backend_factory: object
    inspect_project_namespace_pane_fn: object
    same_tmux_socket_path_fn: object


def _binding_runtime_ref(binding) -> str:
    return str(getattr(binding, "runtime_ref", None) or "").strip()


def _binding_pane_state(binding) -> str:
    return str(getattr(binding, "pane_state", None) or "").strip().lower()


def _is_tmux_binding(binding) -> bool:
    return _binding_runtime_ref(binding).startswith("tmux:")


def _validation_context(
    *,
    tmux_socket_path: str,
    tmux_session_name: str | None,
    agent_name: str,
    project_id: str,
    tmux_backend_factory,
    inspect_project_namespace_pane_fn,
    same_tmux_socket_path_fn,
) -> _BindingValidationContext:
    return _BindingValidationContext(
        tmux_socket_path=tmux_socket_path,
        tmux_session_name=tmux_session_name,
        agent_name=agent_name,
        project_id=project_id,
        tmux_backend_factory=tmux_backend_factory,
        inspect_project_namespace_pane_fn=inspect_project_namespace_pane_fn,
        same_tmux_socket_path_fn=same_tmux_socket_path_fn,
    )


def _matching_namespace_binding(binding, *, context: _BindingValidationContext):
    return matching_project_namespace_record(
        binding=binding,
        tmux_socket_path=context.tmux_socket_path,
        tmux_session_name=context.tmux_session_name,
        agent_name=context.agent_name,
        project_id=context.project_id,
        tmux_backend_factory=context.tmux_backend_factory,
        inspect_project_namespace_pane_fn=context.inspect_project_namespace_pane_fn,
    )


def _binding_matches_project_socket(binding, *, context: _BindingValidationContext) -> bool:
    return context.same_tmux_socket_path_fn(
        getattr(binding, "tmux_socket_path", None),
        context.tmux_socket_path,
    )


def _binding_has_live_namespace_record(binding, *, context: _BindingValidationContext) -> bool:
    return _matching_namespace_binding(binding=binding, context=context) is not None


def _is_live_tmux_binding(binding) -> bool:
    return binding is not None and _is_tmux_binding(binding) and _binding_pane_state(binding) == "alive"


def _has_reusable_tmux_pane(binding) -> bool:
    return binding is not None and _is_tmux_binding(binding) and binding_pane_id(binding) is not None


def _declares_current_project_socket(binding_socket_path: str | None, *, context: _BindingValidationContext) -> bool:
    return context.same_tmux_socket_path_fn(binding_socket_path, context.tmux_socket_path)


def _has_project_tmux_session_name(context: _BindingValidationContext) -> bool:
    return bool(str(context.tmux_session_name or "").strip())


def _usable_project_namespace_binding(binding, *, context: _BindingValidationContext):
    if not _is_live_tmux_binding(binding):
        return None
    if not _binding_matches_project_socket(binding, context=context):
        return None
    if not _binding_has_live_namespace_record(binding, context=context):
        return None
    return binding


def _usable_agent_only_project_binding(binding, *, context: _BindingValidationContext):
    if not _has_reusable_tmux_pane(binding):
        return None

    pane_state = _binding_pane_state(binding)
    binding_socket_declared, binding_socket_path = declared_binding_tmux_socket_path(binding)
    if not binding_socket_declared:
        return binding

    if binding_socket_path and not _declares_current_project_socket(binding_socket_path, context=context):
        return None
    if pane_state in {"dead", "missing", "foreign"}:
        return None

    if _declares_current_project_socket(binding_socket_path, context=context):
        if _binding_has_live_namespace_record(binding, context=context):
            return binding
        if _has_project_tmux_session_name(context):
            return None

    if pane_state in {"", "alive", "unknown"}:
        return binding
    return None


def usable_project_namespace_binding(
    binding,
    *,
    tmux_socket_path: str,
    tmux_session_name: str | None,
    agent_name: str,
    project_id: str,
    tmux_backend_factory,
    inspect_project_namespace_pane_fn,
    same_tmux_socket_path_fn,
) -> object | None:
    context = _validation_context(
        tmux_socket_path=tmux_socket_path,
        tmux_session_name=tmux_session_name,
        agent_name=agent_name,
        project_id=project_id,
        tmux_backend_factory=tmux_backend_factory,
        inspect_project_namespace_pane_fn=inspect_project_namespace_pane_fn,
        same_tmux_socket_path_fn=same_tmux_socket_path_fn,
    )
    return _usable_project_namespace_binding(binding, context=context)


def usable_project_binding(
    binding,
    *,
    cmd_enabled: bool,
    tmux_socket_path: str,
    tmux_session_name: str | None,
    agent_name: str,
    project_id: str,
    tmux_backend_factory,
    inspect_project_namespace_pane_fn,
    same_tmux_socket_path_fn,
):
    context = _validation_context(
        tmux_socket_path=tmux_socket_path,
        tmux_session_name=tmux_session_name,
        agent_name=agent_name,
        project_id=project_id,
        tmux_backend_factory=tmux_backend_factory,
        inspect_project_namespace_pane_fn=inspect_project_namespace_pane_fn,
        same_tmux_socket_path_fn=same_tmux_socket_path_fn,
    )
    if cmd_enabled:
        return _usable_project_namespace_binding(binding, context=context)
    return _usable_agent_only_project_binding(binding, context=context)


def usable_agent_only_project_binding(
    binding,
    *,
    tmux_socket_path: str,
    tmux_session_name: str | None,
    agent_name: str,
    project_id: str,
    tmux_backend_factory,
    inspect_project_namespace_pane_fn,
    same_tmux_socket_path_fn,
):
    context = _validation_context(
        tmux_socket_path=tmux_socket_path,
        tmux_session_name=tmux_session_name,
        agent_name=agent_name,
        project_id=project_id,
        tmux_backend_factory=tmux_backend_factory,
        inspect_project_namespace_pane_fn=inspect_project_namespace_pane_fn,
        same_tmux_socket_path_fn=same_tmux_socket_path_fn,
    )
    return _usable_agent_only_project_binding(binding, context=context)


__all__ = [
    "usable_agent_only_project_binding",
    "usable_project_binding",
    "usable_project_namespace_binding",
]
