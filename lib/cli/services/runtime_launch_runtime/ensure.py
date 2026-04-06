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
    launcher = runtime_launcher(spec.provider)
    if spec.runtime_mode is not RuntimeMode.PANE_BACKED:
        return runtime_launch_result_cls(launched=False, binding=binding)
    if spec.provider not in _PANE_BACKED_RUNTIME_PROVIDERS or launcher is None:
        return runtime_launch_result_cls(launched=False, binding=binding)
    if assigned_pane_id is None and binding is not None and binding.runtime_ref and binding.session_ref and binding_runtime_alive_fn(binding):
        return runtime_launch_result_cls(launched=False, binding=binding)
    if shutil.which('tmux') is None:
        raise RuntimeError(f'tmux is required for pane-backed {spec.provider} launch')
    if shutil.which(provider_executable_fn(spec.provider)) is None:
        raise RuntimeError(f'{spec.provider} executable not found in PATH')
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
    refreshed = resolve_agent_binding_fn(
        provider=spec.provider,
        agent_name=spec.name,
        workspace_path=plan.workspace_path,
        project_root=context.project.project_root,
    )
    if refreshed is None:
        raise RuntimeError(
            f'failed to resolve usable binding for {spec.name} after {spec.provider} launch'
        )
    return runtime_launch_result_cls(launched=True, binding=refreshed)


__all__ = ['ensure_agent_runtime', 'runtime_launcher']
