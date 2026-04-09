from __future__ import annotations

from pathlib import Path

from cli.context import CliContext
from cli.models import ParsedStartCommand
from project.resolver import ProjectContext


def build_start_context(
    *,
    project_root: Path,
    project_id: str,
    paths,
    requested_agents: tuple[str, ...],
    restore: bool,
    auto_permission: bool,
) -> tuple[ParsedStartCommand, CliContext]:
    command = ParsedStartCommand(
        project=str(project_root),
        agent_names=tuple(requested_agents),
        restore=bool(restore),
        auto_permission=bool(auto_permission),
    )
    context = CliContext(
        command=command,
        cwd=project_root,
        project=ProjectContext(
            cwd=project_root,
            project_root=project_root,
            config_dir=paths.ccb_dir,
            project_id=project_id,
            source='ccbd',
        ),
        paths=paths,
    )
    return command, context


def record_namespace_action(
    actions_taken: list[str],
    *,
    tmux_socket_path: str | None,
    tmux_session_name: str | None,
    namespace_epoch: int | None,
) -> None:
    if tmux_socket_path is None or tmux_session_name is None:
        return
    actions_taken.append(
        'ensure_namespace:'
        f'epoch={namespace_epoch if namespace_epoch is not None else "unknown"},'
        f'session={tmux_session_name}'
    )


__all__ = ['build_start_context', 'record_namespace_action']
