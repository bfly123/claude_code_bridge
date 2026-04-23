from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess

from agents.models import AgentSpec
from cli.context import CliContext
from cli.models import ParsedStartCommand
from provider_core.contracts import ProviderRuntimeLauncher
from provider_core.runtime_shared import (
    provider_executable as resolve_provider_executable,
    provider_start_parts as resolve_provider_start_parts,
)
from terminal_runtime import TmuxBackend as _LegacyTmuxBackend, default_mux_backend_cls
from workspace.models import WorkspacePlan

from .provider_hooks import prepare_provider_workspace
from .provider_binding import AgentBinding, resolve_agent_binding
from .runtime_launch_runtime import (
    best_effort_kill_tmux_pane as _best_effort_kill_tmux_pane_impl,
    binding_runtime_alive as _binding_runtime_alive_impl,
    cleanup_stale_tmux_binding as _cleanup_stale_tmux_binding_impl,
    create_detached_tmux_pane as _create_detached_tmux_pane_impl,
    ensure_agent_runtime as _ensure_agent_runtime_impl,
    launch_session_id as _launch_session_id_impl,
    launch_tmux_runtime as _launch_tmux_runtime_impl,
    pane_meets_minimum_size as _pane_meets_minimum_size_impl,
    pane_title_marker as _pane_title_marker_impl,
    runtime_launcher as _runtime_launcher_impl,
    session_filename as _session_filename_impl,
    write_session_file as _write_session_file_impl,
)

TmuxBackend = _LegacyTmuxBackend


def _tmux_backend_cls():
    if TmuxBackend is not _LegacyTmuxBackend:
        return TmuxBackend
    return default_mux_backend_cls()


@dataclass(frozen=True)
class RuntimeLaunchResult:
    launched: bool
    binding: AgentBinding | None


def _runtime_launcher(provider: str) -> ProviderRuntimeLauncher | None:
    return _runtime_launcher_impl(provider)


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
    prepare_provider_workspace(
        layout=context.paths,
        spec=spec,
        workspace_path=plan.workspace_path,
        completion_dir=context.paths.agent_provider_runtime_dir(spec.name, spec.provider) / 'completion',
        agent_name=spec.name,
    )
    return _ensure_agent_runtime_impl(
        context,
        command,
        spec,
        plan,
        binding,
        runtime_launch_result_cls=RuntimeLaunchResult,
        binding_runtime_alive_fn=_binding_runtime_alive,
        provider_executable_fn=_provider_executable,
        cleanup_stale_tmux_binding_fn=_cleanup_stale_tmux_binding,
        launch_tmux_runtime_fn=_launch_tmux_runtime,
        resolve_agent_binding_fn=resolve_agent_binding,
        assigned_pane_id=assigned_pane_id,
        style_index=style_index,
        tmux_socket_path=tmux_socket_path,
    )


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
        backend_factory=_tmux_backend_cls(),
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
    return _binding_runtime_alive_impl(binding, tmux_backend_cls=_tmux_backend_cls())


def _cleanup_stale_tmux_binding(binding: AgentBinding | None) -> None:
    _cleanup_stale_tmux_binding_impl(
        binding,
        tmux_backend_cls=_tmux_backend_cls(),
        kill_tmux_pane_fn=_best_effort_kill_tmux_pane,
    )


def _inside_tmux() -> bool:
    return bool((os.environ.get('TMUX') or os.environ.get('TMUX_PANE') or '').strip())


def _prepare_detached_tmux_server(backend) -> None:
    from .runtime_launch_runtime import prepare_detached_tmux_server as _prepare_detached_tmux_server_impl

    _prepare_detached_tmux_server_impl(backend)


def _create_detached_tmux_pane(backend, *, cmd: str, cwd: Path, session_name: str) -> str:
    return _create_detached_tmux_pane_impl(backend, cmd=cmd, cwd=cwd, session_name=session_name)


def _pane_meets_minimum_size(backend, pane_id: str, *, min_width: int = 20, min_height: int = 8) -> bool:
    return _pane_meets_minimum_size_impl(
        backend,
        pane_id,
        min_width=min_width,
        min_height=min_height,
    )


def _best_effort_kill_tmux_pane(backend, pane_id: str) -> None:
    _best_effort_kill_tmux_pane_impl(backend, pane_id)
