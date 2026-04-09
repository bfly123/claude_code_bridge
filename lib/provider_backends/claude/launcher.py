from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from agents.models import AgentSpec
from cli.context import CliContext
from cli.models import ParsedStartCommand
from provider_backends.runtime_restore import ProviderRestoreTarget
from provider_core.runtime_shared import provider_start_parts
from provider_profiles import ResolvedProviderProfile, load_resolved_provider_profile
from workspace.models import WorkspacePlan

from .launcher_runtime import (
    build_claude_env_prefix as _build_claude_env_prefix_impl,
    build_runtime_launcher as _build_runtime_launcher_impl,
    build_session_payload as _build_session_payload_impl,
    build_start_cmd as _build_start_cmd_impl,
    claude_history_state as _claude_history_state_impl,
    claude_user_base_url as _claude_user_base_url_impl,
    local_tcp_listener_available as _local_tcp_listener_available_impl,
    project_session_restore_target as _project_session_restore_target_impl,
    resolve_claude_restore_target as _resolve_claude_restore_target_impl,
    resolve_run_cwd as _resolve_run_cwd_impl,
    should_drop_claude_base_url as _should_drop_claude_base_url_impl,
    write_claude_settings_overlay as _write_claude_settings_overlay_impl,
)
from .session import load_project_session


def build_runtime_launcher():
    return _build_runtime_launcher_impl(
        build_start_cmd_fn=build_start_cmd,
        build_session_payload_fn=build_session_payload,
        resolve_run_cwd_fn=resolve_run_cwd,
    )


def build_start_cmd(command: ParsedStartCommand, spec: AgentSpec, runtime_dir: Path, launch_session_id: str) -> str:
    return _build_start_cmd_impl(
        command,
        spec,
        runtime_dir,
        launch_session_id,
        load_profile_fn=load_resolved_provider_profile,
        write_settings_overlay_fn=write_claude_settings_overlay,
        build_env_prefix_fn=build_claude_env_prefix,
        resolve_restore_target_fn=_resolve_claude_restore_target,
        provider_start_parts_fn=provider_start_parts,
    )


def resolve_run_cwd(
    command: ParsedStartCommand,
    spec: AgentSpec,
    plan: WorkspacePlan,
    runtime_dir: Path,
    launch_session_id: str,
) -> Path | str | None:
    return _resolve_run_cwd_impl(
        command,
        spec,
        plan,
        runtime_dir,
        launch_session_id,
        resolve_restore_target_fn=_resolve_claude_restore_target,
    )


def build_session_payload(
    context: CliContext,
    spec: AgentSpec,
    plan: WorkspacePlan,
    runtime_dir: Path,
    run_cwd: Path,
    pane_id: str,
    pane_title_marker: str,
    start_cmd: str,
    launch_session_id: str,
    prepared_state: dict[str, object],
) -> dict[str, object]:
    return _build_session_payload_impl(
        context,
        spec,
        plan,
        runtime_dir,
        run_cwd,
        pane_id,
        pane_title_marker,
        start_cmd,
        launch_session_id,
        prepared_state,
    )


def _resolve_claude_restore_target(
    *,
    spec: AgentSpec,
    runtime_dir: Path,
    restore: bool,
    workspace_path: Path | None = None,
) -> ProviderRestoreTarget:
    return _resolve_claude_restore_target_impl(
        spec=spec,
        runtime_dir=runtime_dir,
        restore=restore,
        workspace_path=workspace_path,
        project_session_restore_target_fn=_project_session_restore_target,
        claude_history_state_fn=_claude_history_state,
    )


def _project_session_restore_target(
    workspace_path: Path,
    session_instance: str | None,
) -> ProviderRestoreTarget | None:
    return _project_session_restore_target_impl(
        workspace_path,
        session_instance,
        load_project_session_fn=load_project_session,
        claude_history_state_fn=_claude_history_state,
    )


def _claude_history_state(
    *,
    invocation_dir: Path,
    project_root: Path,
    include_env_pwd: bool,
) -> tuple[str | None, bool, Path | None]:
    return _claude_history_state_impl(
        invocation_dir=invocation_dir,
        project_root=project_root,
        env=os.environ if include_env_pwd else {},
        home_dir=Path.home(),
    )


def write_claude_settings_overlay(
    runtime_dir: Path,
    *,
    profile: ResolvedProviderProfile | None = None,
) -> Path | None:
    return _write_claude_settings_overlay_impl(
        runtime_dir,
        profile=profile,
    )


def build_claude_env_prefix(
    *,
    profile: ResolvedProviderProfile | None = None,
    extra_env: dict[str, str] | None = None,
) -> str:
    return _build_claude_env_prefix_impl(
        profile=profile,
        extra_env=extra_env,
        env=os.environ,
        should_drop_base_url_fn=should_drop_claude_base_url,
        claude_user_base_url_fn=claude_user_base_url,
    )


def claude_user_base_url() -> str:
    return _claude_user_base_url_impl(user_settings_path=Path.home() / '.claude' / 'settings.json')


def should_drop_claude_base_url(value: str) -> bool:
    return _should_drop_claude_base_url_impl(
        value,
        local_tcp_listener_available_fn=local_tcp_listener_available,
    )


def local_tcp_listener_available(host: str, port: int) -> bool:
    return _local_tcp_listener_available_impl(host, port)


__all__ = [
    'build_claude_env_prefix',
    'build_runtime_launcher',
    'build_start_cmd',
    'resolve_run_cwd',
    'write_claude_settings_overlay',
]
