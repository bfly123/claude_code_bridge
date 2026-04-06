from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from provider_profiles.models import ProviderProfileSpec

from ..enums import PermissionMode, QueuePolicy, RestoreMode, RuntimeMode, WorkspaceMode, normalize_runtime_mode
from ..names import SCHEMA_VERSION, AgentValidationError, normalize_agent_name


def normalize_provider_profile(profile) -> ProviderProfileSpec:
    if isinstance(profile, ProviderProfileSpec):
        return profile
    try:
        return ProviderProfileSpec(**dict(profile or {}))
    except Exception as exc:  # pragma: no cover - defensive normalization
        raise AgentValidationError(f'invalid provider_profile: {exc}') from exc


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
        provider = str(self.provider or '').strip().lower()
        if not provider:
            raise AgentValidationError('provider cannot be empty')
        target = str(self.target or '').strip()
        if not target:
            raise AgentValidationError('target cannot be empty')
        object.__setattr__(self, 'provider', provider)
        object.__setattr__(self, 'target', target)
        object.__setattr__(self, 'runtime_mode', normalize_runtime_mode(self.runtime_mode))
        object.__setattr__(self, 'startup_args', tuple(str(item) for item in self.startup_args))
        object.__setattr__(self, 'labels', tuple(str(item) for item in self.labels))
        object.__setattr__(self, 'watch_paths', tuple(str(item) for item in self.watch_paths))
        object.__setattr__(self, 'env', {str(key): str(value) for key, value in dict(self.env).items()})
        object.__setattr__(self, 'provider_profile', normalize_provider_profile(self.provider_profile))

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


__all__ = ['AgentSpec', 'normalize_provider_profile']
