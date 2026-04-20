from __future__ import annotations

from dataclasses import dataclass

from agents.config_loader import load_project_config
from cli.context import CliContext


@dataclass(frozen=True)
class ConfigValidationSummary:
    project_root: str
    project_id: str
    source: str | None
    used_default: bool
    default_agents: tuple[str, ...]
    agent_names: tuple[str, ...]
    cmd_enabled: bool
    layout_spec: str


def validate_config_context(context: CliContext) -> ConfigValidationSummary:
    result = load_project_config(context.project.project_root)
    return ConfigValidationSummary(
        project_root=str(context.project.project_root),
        project_id=context.project.project_id,
        source=str(result.source_path) if result.source_path else None,
        used_default=result.used_default,
        default_agents=result.config.default_agents,
        agent_names=tuple(sorted(result.config.agents)),
        cmd_enabled=bool(result.config.cmd_enabled),
        layout_spec=str(result.config.layout_spec or ''),
    )
