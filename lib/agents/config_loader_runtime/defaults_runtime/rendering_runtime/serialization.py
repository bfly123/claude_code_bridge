from __future__ import annotations

from agents.models import (
    AgentApiSpec,
    PermissionMode,
    ProviderProfileSpec,
    QueuePolicy,
    RestoreMode,
    RuntimeMode,
)
from provider_model_shortcuts import strip_provider_model_startup_args
from provider_profiles import provider_api_env_keys


def agent_spec_to_config_dict(spec) -> dict[str, object]:
    payload: dict[str, object] = {
        'provider': spec.provider,
        'target': spec.target,
        'workspace_mode': spec.workspace_mode.value,
        'runtime_mode': spec.runtime_mode.value,
        'restore': spec.restore_default.value,
        'permission': spec.permission_default.value,
        'queue_policy': spec.queue_policy.value,
    }
    update_optional_agent_fields(payload, spec)
    return payload


def update_optional_agent_fields(payload: dict[str, object], spec) -> None:
    if spec.workspace_root is not None:
        payload['workspace_root'] = spec.workspace_root
    if spec.model is not None:
        payload['model'] = spec.model
    startup_args = _config_startup_args(spec)
    if startup_args:
        payload['startup_args'] = list(startup_args)
    if spec.env:
        payload['env'] = dict(spec.env)
    if spec.api != AgentApiSpec():
        payload.update(spec.api.to_record())
    provider_profile_payload = _provider_profile_config_dict(spec)
    if provider_profile_payload is not None:
        payload['provider_profile'] = provider_profile_payload
    if spec.branch_template is not None:
        payload['branch_template'] = spec.branch_template
    if spec.labels:
        payload['labels'] = list(spec.labels)
    if spec.description is not None:
        payload['description'] = spec.description
    if spec.watch_paths:
        payload['watch_paths'] = list(spec.watch_paths)


def agent_spec_to_hybrid_overlay_dict(
    spec,
    *,
    compact_provider: str,
    compact_workspace_mode: str,
) -> dict[str, object]:
    payload = agent_spec_to_config_dict(spec)
    defaults = {
        'provider': compact_provider,
        'target': '.',
        'workspace_mode': compact_workspace_mode,
        'runtime_mode': RuntimeMode.PANE_BACKED.value,
        'restore': RestoreMode.AUTO.value,
        'permission': PermissionMode.MANUAL.value,
        'queue_policy': QueuePolicy.SERIAL_PER_AGENT.value,
    }
    for key, expected in defaults.items():
        if payload.get(key) == expected:
            payload.pop(key, None)
    return payload


def _provider_profile_config_dict(spec) -> dict[str, object] | None:
    profile = spec.provider_profile
    default_profile = ProviderProfileSpec()
    if spec.api == AgentApiSpec():
        if profile == default_profile:
            return None
        return profile.to_record()

    filtered_env = {
        key: value
        for key, value in profile.env.items()
        if key not in provider_api_env_keys(spec.provider)
    }
    payload: dict[str, object] = {}
    if profile.mode != default_profile.mode:
        payload['mode'] = profile.mode
    if profile.home is not None:
        payload['home'] = profile.home
    if filtered_env:
        payload['env'] = filtered_env
    if profile.inherit_auth != default_profile.inherit_auth:
        payload['inherit_auth'] = profile.inherit_auth
    if profile.inherit_config != default_profile.inherit_config:
        payload['inherit_config'] = profile.inherit_config
    if profile.inherit_skills != default_profile.inherit_skills:
        payload['inherit_skills'] = profile.inherit_skills
    if profile.inherit_commands != default_profile.inherit_commands:
        payload['inherit_commands'] = profile.inherit_commands
    return payload or None


def _config_startup_args(spec) -> tuple[str, ...]:
    if spec.model is None:
        return tuple(spec.startup_args)
    return strip_provider_model_startup_args(spec.provider, spec.startup_args, model=spec.model)


__all__ = ['agent_spec_to_config_dict', 'agent_spec_to_hybrid_overlay_dict', 'update_optional_agent_fields']
