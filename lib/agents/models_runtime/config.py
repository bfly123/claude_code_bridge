from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from provider_profiles.models import ProviderProfileSpec

from .layout import build_balanced_layout, parse_layout_spec
from .enums import PermissionMode, QueuePolicy, RestoreMode, RuntimeMode, WorkspaceMode, normalize_runtime_mode
from .names import SCHEMA_VERSION, AgentValidationError, normalize_agent_name


@dataclass(frozen=True)
class AgentSpec:
    name: str
    provider: str
    target: str
    workspace_mode: WorkspaceMode
    workspace_root: str | None
    runtime_mode: RuntimeMode
    restore_default: RestoreMode
    permission_default: PermissionMode
    queue_policy: QueuePolicy
    startup_args: tuple[str, ...] = field(default_factory=tuple)
    env: dict[str, str] = field(default_factory=dict)
    provider_profile: ProviderProfileSpec = field(default_factory=ProviderProfileSpec)
    branch_template: str | None = None
    labels: tuple[str, ...] = field(default_factory=tuple)
    description: str | None = None
    watch_paths: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, 'name', normalize_agent_name(self.name))
        provider = (self.provider or '').strip().lower()
        if not provider:
            raise AgentValidationError('provider cannot be empty')
        object.__setattr__(self, 'provider', provider)
        target = (self.target or '').strip()
        if not target:
            raise AgentValidationError('target cannot be empty')
        object.__setattr__(self, 'target', target)
        object.__setattr__(self, 'runtime_mode', normalize_runtime_mode(self.runtime_mode))
        object.__setattr__(self, 'startup_args', tuple(str(item) for item in self.startup_args))
        object.__setattr__(self, 'labels', tuple(str(item) for item in self.labels))
        object.__setattr__(self, 'watch_paths', tuple(str(item) for item in self.watch_paths))
        object.__setattr__(self, 'env', {str(key): str(value) for key, value in dict(self.env).items()})
        profile = self.provider_profile
        if not isinstance(profile, ProviderProfileSpec):
            try:
                profile = ProviderProfileSpec(**dict(profile or {}))
            except Exception as exc:  # pragma: no cover - defensive normalization
                raise AgentValidationError(f'invalid provider_profile: {exc}') from exc
        object.__setattr__(self, 'provider_profile', profile)

    def to_record(self) -> dict[str, Any]:
        return {
            'schema_version': SCHEMA_VERSION,
            'record_type': 'agent_spec',
            'name': self.name,
            'provider': self.provider,
            'target': self.target,
            'workspace_mode': self.workspace_mode.value,
            'workspace_root': self.workspace_root,
            'runtime_mode': self.runtime_mode.value,
            'restore_default': self.restore_default.value,
            'permission_default': self.permission_default.value,
            'queue_policy': self.queue_policy.value,
            'startup_args': list(self.startup_args),
            'env': dict(self.env),
            'provider_profile': self.provider_profile.to_record(),
            'branch_template': self.branch_template,
            'labels': list(self.labels),
            'description': self.description,
            'watch_paths': list(self.watch_paths),
        }


@dataclass(frozen=True)
class ProjectConfig:
    version: int
    default_agents: tuple[str, ...]
    agents: dict[str, AgentSpec]
    cmd_enabled: bool = False
    layout_spec: str | None = None
    source_path: str | None = None

    def __post_init__(self) -> None:
        if self.version != SCHEMA_VERSION:
            raise AgentValidationError(f'version must be {SCHEMA_VERSION}')
        normalized_agents: dict[str, AgentSpec] = {}
        for key, spec in dict(self.agents).items():
            normalized_key = normalize_agent_name(key)
            if normalized_key in normalized_agents:
                raise AgentValidationError(f'duplicate agent {normalized_key!r}')
            if spec.name != normalized_key:
                raise AgentValidationError(
                    f'agent key {normalized_key!r} does not match spec name {spec.name!r}'
                )
            normalized_agents[normalized_key] = spec
        if not normalized_agents:
            raise AgentValidationError('at least one agent must be configured')
        defaults = tuple(normalize_agent_name(item) for item in self.default_agents)
        if not defaults:
            raise AgentValidationError('default_agents cannot be empty')
        if len(set(defaults)) != len(defaults):
            raise AgentValidationError('default_agents cannot contain duplicates')
        missing = [name for name in defaults if name not in normalized_agents]
        if missing:
            raise AgentValidationError(f'default_agents reference unknown agents: {missing}')
        layout_spec = str(self.layout_spec or '').strip()
        if not layout_spec:
            layout_spec = build_balanced_layout(
                defaults,
                providers_by_agent={name: normalized_agents[name].provider for name in defaults},
                cmd_enabled=bool(self.cmd_enabled),
            ).render()
        try:
            layout = parse_layout_spec(layout_spec)
        except Exception as exc:
            raise AgentValidationError(f'invalid layout_spec: {exc}') from exc
        layout_names = tuple(leaf.name for leaf in layout.iter_leaves())
        expected_names = set(defaults)
        if self.cmd_enabled:
            expected_names.add('cmd')
        if set(layout_names) != expected_names:
            raise AgentValidationError(
                'layout_spec must include each configured agent exactly once'
                + (' and cmd' if self.cmd_enabled else '')
            )
        if len(set(layout_names)) != len(layout_names):
            raise AgentValidationError('layout_spec cannot contain duplicate leaves')
        if self.cmd_enabled and layout_names[0] != 'cmd':
            raise AgentValidationError('layout_spec must anchor cmd as the first pane when cmd_enabled=true')
        object.__setattr__(self, 'default_agents', defaults)
        object.__setattr__(self, 'agents', normalized_agents)
        object.__setattr__(self, 'layout_spec', layout.render())

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


__all__ = ['AgentSpec', 'ProjectConfig']
