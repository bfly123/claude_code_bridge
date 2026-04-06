from __future__ import annotations

from pathlib import Path

from agents.models import AgentSpec
from cli.context import CliContext
from cli.models import ParsedStartCommand
from provider_core.contracts import ProviderRuntimeLauncher
from workspace.models import WorkspacePlan
from .launcher_runtime import build_start_cmd as _build_start_cmd_impl
from .launcher_runtime import post_launch as _post_launch_impl
from .launcher_runtime import prepare_runtime as _prepare_runtime_impl


def build_runtime_launcher() -> ProviderRuntimeLauncher:
    return ProviderRuntimeLauncher(
        provider='codex',
        launch_mode='codex_tmux',
        prepare_runtime=prepare_runtime,
        build_start_cmd=build_start_cmd,
        build_session_payload=build_session_payload,
        post_launch=post_launch,
    )


def prepare_runtime(runtime_dir: Path) -> dict[str, object]:
    return _prepare_runtime_impl(runtime_dir)


def build_start_cmd(command: ParsedStartCommand, spec: AgentSpec, runtime_dir: Path, launch_session_id: str) -> str:
    return _build_start_cmd_impl(command, spec, runtime_dir, launch_session_id)


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
    input_fifo = Path(prepared_state['input_fifo'])
    output_fifo = Path(prepared_state['output_fifo'])
    return {
        'ccb_session_id': launch_session_id,
        'agent_name': spec.name,
        'ccb_project_id': context.project.project_id,
        'runtime_dir': str(runtime_dir),
        'completion_artifact_dir': str(runtime_dir / 'completion'),
        'input_fifo': str(input_fifo),
        'output_fifo': str(output_fifo),
        'terminal': 'tmux',
        'tmux_session': pane_id,
        'pane_id': pane_id,
        'pane_title_marker': pane_title_marker,
        'tmux_log': str(runtime_dir / 'bridge_output.log'),
        'workspace_path': str(plan.workspace_path),
        'work_dir': str(run_cwd),
        'start_dir': str(context.project.project_root),
        'codex_start_cmd': start_cmd,
        'start_cmd': start_cmd,
    }


def post_launch(backend: object, pane_id: str, runtime_dir: Path, launch_session_id: str, prepared_state: dict[str, object]) -> None:
    _post_launch_impl(backend, pane_id, runtime_dir, launch_session_id, prepared_state)


__all__ = ['build_runtime_launcher', 'build_start_cmd']
