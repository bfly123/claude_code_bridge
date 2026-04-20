from __future__ import annotations

import shutil

from agents.models import RuntimeMode
from provider_core.registry import CORE_PROVIDER_NAMES, OPTIONAL_PROVIDER_NAMES, build_default_runtime_launcher_map


_PANE_BACKED_RUNTIME_PROVIDERS = frozenset(CORE_PROVIDER_NAMES + OPTIONAL_PROVIDER_NAMES)


def runtime_launcher(provider: str):
    return build_default_runtime_launcher_map(include_optional=True).get(str(provider or '').strip().lower())


def ensure_agent_runtime(
    context,
    command,
    spec,
    plan,
    binding,
    *,
    runtime_launch_result_cls,
    binding_runtime_alive_fn,
    provider_executable_fn,
    cleanup_stale_tmux_binding_fn,
    launch_tmux_runtime_fn,
    resolve_agent_binding_fn,
    assigned_pane_id: str | None = None,
    style_index: int = 0,
    tmux_socket_path: str | None = None,
):
    launcher = _pane_backed_launcher(spec)
    if launcher is None:
        return runtime_launch_result_cls(launched=False, binding=binding)
    if _binding_is_reusable(
        binding=binding,
        assigned_pane_id=assigned_pane_id,
        binding_runtime_alive_fn=binding_runtime_alive_fn,
    ):
        return runtime_launch_result_cls(launched=False, binding=binding)
    _require_runtime_launch_tools(
        spec.provider,
        provider_executable_fn=provider_executable_fn,
    )
    cleanup_stale_tmux_binding_fn(binding)

    launch_tmux_runtime_fn(
        context,
        command,
        spec,
        plan,
        launcher,
        assigned_pane_id=assigned_pane_id,
        style_index=style_index,
        tmux_socket_path=tmux_socket_path,
    )
    refreshed = _resolve_refreshed_binding(
        context=context,
        spec=spec,
        plan=plan,
        resolve_agent_binding_fn=resolve_agent_binding_fn,
    )
    return runtime_launch_result_cls(launched=True, binding=refreshed)


def _pane_backed_launcher(spec):
    if spec.runtime_mode is not RuntimeMode.PANE_BACKED:
        return None
    if spec.provider not in _PANE_BACKED_RUNTIME_PROVIDERS:
        return None
    return runtime_launcher(spec.provider)


def _binding_is_reusable(
    *,
    binding,
    assigned_pane_id: str | None,
    binding_runtime_alive_fn,
) -> bool:
    if assigned_pane_id is not None or binding is None:
        return False
    if not binding.runtime_ref or not binding.session_ref:
        return False
    return bool(binding_runtime_alive_fn(binding))


def _require_runtime_launch_tools(provider: str, *, provider_executable_fn) -> None:
    if shutil.which('tmux') is None:
        raise RuntimeError(f'tmux is required for pane-backed {provider} launch')
    if shutil.which(provider_executable_fn(provider)) is None:
        raise RuntimeError(f'{provider} executable not found in PATH')


def _resolve_refreshed_binding(*, context, spec, plan, resolve_agent_binding_fn):
    refreshed = resolve_agent_binding_fn(
        provider=spec.provider,
        agent_name=spec.name,
        workspace_path=plan.workspace_path,
        project_root=context.project.project_root,
    )
    if refreshed is not None:
        return refreshed
    raise RuntimeError(
        f'failed to resolve usable binding for {spec.name} after {spec.provider} launch'
    )


__all__ = ['ensure_agent_runtime', 'runtime_launcher']
