from __future__ import annotations

from pathlib import Path
import shlex

from agents.models import AgentSpec
from cli.context import CliContext
from cli.models import ParsedStartCommand
from provider_core.contracts import ProviderRuntimeLauncher
from provider_core.runtime_shared import provider_start_parts
from provider_profiles import load_resolved_provider_profile
from workspace.models import WorkspacePlan

from .env import build_gemini_env_prefix


def build_runtime_launcher(
    *,
    build_start_cmd_fn,
    build_session_payload_fn,
    resolve_run_cwd_fn,
) -> ProviderRuntimeLauncher:
    return ProviderRuntimeLauncher(
        provider="gemini",
        launch_mode="simple_tmux",
        build_start_cmd=build_start_cmd_fn,
        build_session_payload=build_session_payload_fn,
        resolve_run_cwd=resolve_run_cwd_fn,
    )


def build_start_cmd(
    command: ParsedStartCommand,
    spec: AgentSpec,
    runtime_dir,
    launch_session_id: str,
    *,
    resolve_restore_target_fn,
) -> str:
    del launch_session_id
    runtime_dir = Path(runtime_dir)
    profile = load_resolved_provider_profile(runtime_dir)
    restore_target = resolve_restore_target_fn(
        spec=spec,
        runtime_dir=runtime_dir,
        restore=command.restore,
    )
    cmd_parts = provider_start_parts("gemini")
    if command.auto_permission:
        cmd_parts.append("--yolo")
    if restore_target.has_history:
        cmd_parts.extend(["--resume", "latest"])
    cmd_parts.extend(spec.startup_args)
    cmd = " ".join(shlex.quote(str(part)) for part in cmd_parts)
    env_prefix = build_gemini_env_prefix(profile=profile, extra_env=spec.env)
    if env_prefix:
        return f"{env_prefix}; {cmd}"
    return cmd


def resolve_run_cwd(
    command: ParsedStartCommand,
    spec: AgentSpec,
    plan: WorkspacePlan,
    runtime_dir: Path,
    launch_session_id: str,
    *,
    resolve_restore_target_fn,
) -> Path | str | None:
    del launch_session_id
    return resolve_restore_target_fn(
        spec=spec,
        runtime_dir=runtime_dir,
        workspace_path=plan.workspace_path,
        restore=command.restore,
    ).run_cwd


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
    del prepared_state
    runtime_dir = Path(runtime_dir)
    return {
        "ccb_session_id": launch_session_id,
        "agent_name": spec.name,
        "ccb_project_id": context.project.project_id,
        "runtime_dir": str(runtime_dir),
        "completion_artifact_dir": str(runtime_dir / "completion"),
        "terminal": "tmux",
        "tmux_session": pane_id,
        "pane_id": pane_id,
        "pane_title_marker": pane_title_marker,
        "workspace_path": str(plan.workspace_path),
        "work_dir": str(run_cwd),
        "start_dir": str(context.project.project_root),
        "start_cmd": start_cmd,
    }


__all__ = [
    "build_runtime_launcher",
    "build_session_payload",
    "build_start_cmd",
    "resolve_run_cwd",
]
