from __future__ import annotations

import json

from ..project import build_default_project_config
from .compact import can_render_compact
from .serialization import agent_spec_to_config_dict


def render_default_project_config_text() -> str:
    return render_project_config_text(build_default_project_config())


def render_project_config_text(config) -> str:
    if can_render_compact(config):
        return f'{config.layout_spec}\n'
    payload = {
        'version': config.version,
        'default_agents': list(config.default_agents),
        'cmd_enabled': bool(config.cmd_enabled),
        'layout': config.layout_spec,
        'agents': {name: agent_spec_to_config_dict(spec) for name, spec in config.agents.items()},
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + '\n'


__all__ = ['render_default_project_config_text', 'render_project_config_text']
