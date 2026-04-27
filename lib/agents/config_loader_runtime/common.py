from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agents.models import ProjectConfig

CONFIG_FILENAME = 'ccb.config'
DEFAULT_AGENT_ORDER = ('agent1', 'agent2', 'agent3')
DEFAULT_DEFAULT_AGENTS = DEFAULT_AGENT_ORDER
ALLOWED_TOP_LEVEL_KEYS = {'version', 'default_agents', 'agents', 'cmd_enabled', 'layout'}
ALLOWED_PROVIDER_PROFILE_KEYS = {
    'mode',
    'home',
    'env',
    'inherit_api',
    'inherit_auth',
    'inherit_config',
    'inherit_skills',
    'inherit_commands',
}
ALLOWED_AGENT_KEYS = {
    'provider',
    'target',
    'workspace_mode',
    'workspace_root',
    'runtime_mode',
    'restore',
    'permission',
    'queue_policy',
    'model',
    'key',
    'url',
    'startup_args',
    'env',
    'api',
    'provider_profile',
    'branch_template',
    'labels',
    'description',
    'watch_paths',
}


class ConfigValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ConfigLoadResult:
    config: ProjectConfig
    source_path: Path | None
    used_default: bool = False


__all__ = [
    'ALLOWED_AGENT_KEYS',
    'ALLOWED_PROVIDER_PROFILE_KEYS',
    'ALLOWED_TOP_LEVEL_KEYS',
    'CONFIG_FILENAME',
    'DEFAULT_AGENT_ORDER',
    'DEFAULT_DEFAULT_AGENTS',
    'ConfigLoadResult',
    'ConfigValidationError',
]
