from __future__ import annotations

from agents.models import ProviderProfileSpec


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
    if spec.startup_args:
        payload['startup_args'] = list(spec.startup_args)
    if spec.env:
        payload['env'] = dict(spec.env)
    if spec.provider_profile != ProviderProfileSpec():
        payload['provider_profile'] = spec.provider_profile.to_record()
    if spec.branch_template is not None:
        payload['branch_template'] = spec.branch_template
    if spec.labels:
        payload['labels'] = list(spec.labels)
    if spec.description is not None:
        payload['description'] = spec.description
    if spec.watch_paths:
        payload['watch_paths'] = list(spec.watch_paths)


__all__ = ['agent_spec_to_config_dict', 'update_optional_agent_fields']
