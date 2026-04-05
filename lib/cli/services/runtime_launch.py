from __future__ import annotations

from dataclasses import dataclass
import os
import shutil
import subprocess
from pathlib import Path

from agents.models import AgentSpec, RuntimeMode
from cli.context import CliContext
from cli.models import ParsedStartCommand
from provider_core.contracts import ProviderRuntimeLauncher
from provider_core.runtime_shared import (
    provider_executable as resolve_provider_executable,
    provider_start_parts as resolve_provider_start_parts,
)
from provider_core.registry import (
    CORE_PROVIDER_NAMES,
    OPTIONAL_PROVIDER_NAMES,
    build_default_runtime_launcher_map,
)
from terminal_runtime import TmuxBackend
from workspace.models import WorkspacePlan

from .provider_binding import AgentBinding, resolve_agent_binding
from .runtime_launch_runtime import (
    best_effort_kill_tmux_pane as _best_effort_kill_tmux_pane_impl,
    create_detached_tmux_pane as _create_detached_tmux_pane_impl,
    launch_session_id as _launch_session_id_impl,
    launch_tmux_runtime as _launch_tmux_runtime_impl,
    pane_meets_minimum_size as _pane_meets_minimum_size_impl,
    pane_title_marker as _pane_title_marker_impl,
    session_filename as _session_filename_impl,
    write_session_file as _write_session_file_impl,
)


@dataclass(frozen=True)
class RuntimeLaunchResult:
    launched: bool
    binding: AgentBinding | None


_PANE_BACKED_RUNTIME_PROVIDERS = frozenset(CORE_PROVIDER_NAMES + OPTIONAL_PROVIDER_NAMES)


def _runtime_launcher(provider: str) -> ProviderRuntimeLauncher | None:
    return build_default_runtime_launcher_map(include_optional=True).get(str(provider or '').strip().lower())


def ensure_agent_runtime(
    context: CliContext,
    command: ParsedStartCommand,
    spec: AgentSpec,
    plan: WorkspacePlan,
    binding: AgentBinding | None,
    *,
    assigned_pane_id: str | None = None,
    style_index: int = 0,
    tmux_socket_path: str | None = None,
) -> RuntimeLaunchResult:
    launcher = _runtime_launcher(spec.provider)
    if spec.runtime_mode is not RuntimeMode.PANE_BACKED:
        return RuntimeLaunchResult(launched=False, binding=binding)
    if spec.provider not in _PANE_BACKED_RUNTIME_PROVIDERS or launcher is None:
        return RuntimeLaunchResult(launched=False, binding=binding)
    if assigned_pane_id is None and binding is not None and binding.runtime_ref and binding.session_ref and _binding_runtime_alive(binding):
        return RuntimeLaunchResult(launched=False, binding=binding)
    if shutil.which('tmux') is None:
        raise RuntimeError(f'tmux is required for pane-backed {spec.provider} launch')
    if shutil.which(_provider_executable(spec.provider)) is None:
        raise RuntimeError(f'{spec.provider} executable not found in PATH')
    _cleanup_stale_tmux_binding(binding)

    _launch_tmux_runtime(
        context,
        command,
        spec,
        plan,
        launcher,
        assigned_pane_id=assigned_pane_id,
        style_index=style_index,
        tmux_socket_path=tmux_socket_path,
    )
    refreshed = resolve_agent_binding(
        provider=spec.provider,
        agent_name=spec.name,
        workspace_path=plan.workspace_path,
        project_root=context.project.project_root,
    )
    if refreshed is None:
        raise RuntimeError(
            f'failed to resolve usable binding for {spec.name} after {spec.provider} launch'
        )
    return RuntimeLaunchResult(launched=True, binding=refreshed)


def _launch_tmux_runtime(
    context: CliContext,
    command: ParsedStartCommand,
    spec: AgentSpec,
    plan: WorkspacePlan,
    launcher: ProviderRuntimeLauncher,
    *,
    assigned_pane_id: str | None = None,
    style_index: int = 0,
    tmux_socket_path: str | None = None,
) -> None:
    _launch_tmux_runtime_impl(
        context,
        command,
        spec,
        plan,
        launcher,
        backend_factory=TmuxBackend,
        pane_title_marker_fn=_pane_title_marker,
        launch_session_id_fn=_launch_session_id,
        create_detached_tmux_pane_fn=_create_detached_tmux_pane,
        pane_meets_minimum_size_fn=_pane_meets_minimum_size,
        best_effort_kill_tmux_pane_fn=_best_effort_kill_tmux_pane,
        write_session_file_fn=_write_session_file,
        assigned_pane_id=assigned_pane_id,
        style_index=style_index,
        tmux_socket_path=tmux_socket_path,
        allow_detached_fallback=tmux_socket_path is None,
    )


def _write_session_file(
    *,
    context: CliContext,
    spec: AgentSpec,
    plan: WorkspacePlan,
    runtime_dir: Path,
    run_cwd: Path,
    pane_id: str,
    tmux_socket_name: str | None,
    tmux_socket_path: str | None,
    pane_title_marker: str,
    start_cmd: str,
    launch_session_id: str,
    provider_payload: dict[str, object],
) -> Path:
    return _write_session_file_impl(
        context=context,
        spec=spec,
        plan=plan,
        runtime_dir=runtime_dir,
        run_cwd=run_cwd,
        pane_id=pane_id,
        tmux_socket_name=tmux_socket_name,
        tmux_socket_path=tmux_socket_path,
        pane_title_marker=pane_title_marker,
        start_cmd=start_cmd,
        launch_session_id=launch_session_id,
        provider_payload=provider_payload,
    )


def _launch_session_id(agent_name: str) -> str:
    return _launch_session_id_impl(agent_name)


def _session_filename(spec: AgentSpec) -> str:
    return _session_filename_impl(spec)


def _provider_executable(provider: str) -> str:
    return resolve_provider_executable(provider)


def _provider_start_parts(provider: str) -> list[str]:
    return resolve_provider_start_parts(provider)


def _pane_title_marker(context: CliContext, spec: AgentSpec) -> str:
    return _pane_title_marker_impl(context, spec)


def _binding_runtime_alive(binding: AgentBinding) -> bool:
    runtime_ref = str(binding.runtime_ref or '').strip()
    if not runtime_ref:
        return False
    if runtime_ref.startswith('tmux:'):
        pane_state = str(binding.pane_state or '').strip().lower()
        if pane_state not in {'', 'alive'}:
            return False
        target = str(binding.active_pane_id or binding.pane_id or runtime_ref[len('tmux:') :]).strip()
        try:
            backend = TmuxBackend(socket_name=binding.tmux_socket_name, socket_path=binding.tmux_socket_path)
        except TypeError:
            backend = TmuxBackend()
        if target.startswith('%'):
            try:
                return backend.is_tmux_pane_alive(target)
            except Exception:
                return False
        return False
    return True




def _cleanup_stale_tmux_binding(binding: AgentBinding | None) -> None:
    if binding is None:
        return
    runtime_ref = str(binding.runtime_ref or '').strip()
    if not runtime_ref.startswith('tmux:'):
        return
    pane_state = str(binding.pane_state or '').strip().lower()
    if pane_state not in {'dead', 'missing'}:
        return
    pane_id = str(binding.pane_id or binding.active_pane_id or '').strip()
    if not pane_id.startswith('%'):
        return
    try:
        backend = TmuxBackend(socket_name=binding.tmux_socket_name, socket_path=binding.tmux_socket_path)
    except TypeError:
        backend = TmuxBackend()
    except Exception:
        return
    _best_effort_kill_tmux_pane(backend, pane_id)

def _inside_tmux() -> bool:
    return bool((os.environ.get('TMUX') or os.environ.get('TMUX_PANE') or '').strip())


def _prepare_detached_tmux_server(backend: TmuxBackend) -> None:
    from .runtime_launch_runtime import prepare_detached_tmux_server as _prepare_detached_tmux_server_impl

    _prepare_detached_tmux_server_impl(backend)


def _create_detached_tmux_pane(backend: TmuxBackend, *, cmd: str, cwd: Path, session_name: str) -> str:
    return _create_detached_tmux_pane_impl(backend, cmd=cmd, cwd=cwd, session_name=session_name)


def _pane_meets_minimum_size(backend: TmuxBackend, pane_id: str, *, min_width: int = 20, min_height: int = 8) -> bool:
    return _pane_meets_minimum_size_impl(
        backend,
        pane_id,
        min_width=min_width,
        min_height=min_height,
    )


def _best_effort_kill_tmux_pane(backend: TmuxBackend, pane_id: str) -> None:
    _best_effort_kill_tmux_pane_impl(backend, pane_id)
