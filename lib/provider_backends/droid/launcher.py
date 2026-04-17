from __future__ import annotations

import shlex
from pathlib import Path

from agents.models import AgentSpec
from cli.context import CliContext
from cli.models import ParsedStartCommand
from provider_core.caller_env import caller_context_env, export_env_clause
from provider_core.contracts import ProviderRuntimeLauncher
from provider_core.runtime_shared import provider_start_parts
from workspace.models import WorkspacePlan


def build_runtime_launcher() -> ProviderRuntimeLauncher:
    return ProviderRuntimeLauncher(
        provider='droid',
        launch_mode='simple_tmux',
        build_start_cmd=build_start_cmd,
        build_session_payload=build_session_payload,
    )


def build_start_cmd(command: ParsedStartCommand, spec: AgentSpec, runtime_dir, launch_session_id: str) -> str:
    cmd_parts = provider_start_parts('droid')
    if command.restore:
        cmd_parts.append('-r')
    cmd_parts.extend(spec.startup_args)
    cmd = ' '.join(shlex.quote(str(part)) for part in cmd_parts)
    env_prefix = export_env_clause(
        caller_context_env(actor=spec.name, runtime_dir=Path(runtime_dir), launch_session_id=launch_session_id)
    )
    if env_prefix:
        return f'{env_prefix}; {cmd}'
    return cmd


def build_session_payload(
    context: CliContext,
    spec: AgentSpec,
    plan: WorkspacePlan,
    runtime_dir,
    run_cwd,
    pane_id: str,
    pane_title_marker: str,
    start_cmd: str,
    launch_session_id: str,
    prepared_state: dict[str, object],
) -> dict[str, object]:
    del prepared_state
    return {
        'ccb_session_id': launch_session_id,
        'agent_name': spec.name,
        'ccb_project_id': context.project.project_id,
        'runtime_dir': str(runtime_dir),
        'completion_artifact_dir': str(runtime_dir / 'completion'),
        'terminal': 'tmux',
        'tmux_session': pane_id,
        'pane_id': pane_id,
        'pane_title_marker': pane_title_marker,
        'workspace_path': str(plan.workspace_path),
        'work_dir': str(run_cwd),
        'start_dir': str(context.project.project_root),
        'start_cmd': start_cmd,
    }


__all__ = ['build_runtime_launcher', 'build_start_cmd']
