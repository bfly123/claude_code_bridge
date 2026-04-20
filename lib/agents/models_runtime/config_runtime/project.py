from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..names import SCHEMA_VERSION, AgentValidationError
from .validation import normalize_agent_specs, normalize_default_agents, resolve_layout_spec


@dataclass(frozen=True)
class ProjectConfig:
    version: int
    default_agents: tuple[str, ...]
    agents: dict[str, object]
    cmd_enabled: bool = False
    layout_spec: str | None = None
    source_path: str | None = None

    def __post_init__(self) -> None:
        if self.version != SCHEMA_VERSION:
            raise AgentValidationError(f'version must be {SCHEMA_VERSION}')
        normalized_agents = normalize_agent_specs(self.agents)
        defaults = normalize_default_agents(self.default_agents, normalized_agents=normalized_agents)
        rendered_layout = resolve_layout_spec(
            default_agents=defaults,
            normalized_agents=normalized_agents,
            cmd_enabled=bool(self.cmd_enabled),
            layout_spec=self.layout_spec,
        )
        object.__setattr__(self, 'default_agents', defaults)
        object.__setattr__(self, 'agents', normalized_agents)
        object.__setattr__(self, 'layout_spec', rendered_layout)

    def to_record(self) -> dict[str, Any]:
        return {
            'schema_version': SCHEMA_VERSION,
            'record_type': 'project_config',
            'version': self.version,
            'default_agents': list(self.default_agents),
            'agents': {name: spec.to_record() for name, spec in self.agents.items()},
            'cmd_enabled': bool(self.cmd_enabled),
            'layout_spec': self.layout_spec,
            'source_path': self.source_path,
        }


__all__ = ['ProjectConfig']
