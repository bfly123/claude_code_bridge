from __future__ import annotations

from pathlib import Path

from agents.models import AgentSpec
from cli.context import CliContext
from cli.models import ParsedStartCommand
from provider_backends.runtime_restore import ProviderRestoreTarget
from provider_profiles import ResolvedProviderProfile
from workspace.models import WorkspacePlan

from .launcher_runtime import (
    build_gemini_env_prefix as _build_gemini_env_prefix_impl,
    build_runtime_launcher as _build_runtime_launcher_impl,
    build_session_payload as _build_session_payload_impl,
    build_start_cmd as _build_start_cmd_impl,
    resolve_gemini_restore_target as _resolve_gemini_restore_target_impl,
    resolve_run_cwd as _resolve_run_cwd_impl,
)
from .session import load_project_session


def build_runtime_launcher():
    return _build_runtime_launcher_impl(
        build_start_cmd_fn=build_start_cmd,
        build_session_payload_fn=build_session_payload,
        resolve_run_cwd_fn=resolve_run_cwd,
    )


def build_start_cmd(
    command: ParsedStartCommand,
    spec: AgentSpec,
    runtime_dir,
    launch_session_id: str,
) -> str:
    return _build_start_cmd_impl(
        command,
        spec,
        runtime_dir,
        launch_session_id,
        resolve_restore_target_fn=_resolve_gemini_restore_target,
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
        resolve_restore_target_fn=_resolve_gemini_restore_target,
    )


def build_session_payload(
    context: CliContext,
    spec: AgentSpec,
    plan: WorkspacePlan,
    runtime_dir,
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


def _resolve_gemini_restore_target(
    *,
    spec: AgentSpec,
    runtime_dir: Path,
    restore: bool,
    workspace_path: Path | None = None,
) -> ProviderRestoreTarget:
    return _resolve_gemini_restore_target_impl(
        spec=spec,
        runtime_dir=runtime_dir,
        restore=restore,
        workspace_path=workspace_path,
        load_project_session_fn=load_project_session,
    )


def build_gemini_env_prefix(
    *,
    profile: ResolvedProviderProfile | None = None,
    extra_env: dict[str, str] | None = None,
) -> str:
    return _build_gemini_env_prefix_impl(profile=profile, extra_env=extra_env)


__all__ = ["build_gemini_env_prefix", "build_runtime_launcher", "build_start_cmd", "resolve_run_cwd"]
