from __future__ import annotations

from pathlib import Path
from typing import Any

from provider_profiles import ResolvedProviderProfile, provider_api_env_keys

from .common import load_json, save_json, workspace_key


def install_claude_hooks(*, workspace_path: Path, command: str) -> Path:
    settings_path = _workspace_settings_path(
        workspace_path,
        filename='settings.local.json',
    )
    data = _load_settings(settings_path)
    hooks = _hooks_payload(data)
    groups = _event_groups(hooks, event_name='Stop')
    if not claude_event_has_command(groups, command):
        groups.append(_command_hook_group(command))
    hooks['Stop'] = groups
    return save_json(settings_path, data)


def sync_claude_workspace_settings(
    *,
    workspace_path: Path,
    resolved_profile: ResolvedProviderProfile | None = None,
) -> Path | None:
    user_settings_path = Path.home() / '.claude' / 'settings.json'
    user_data = _load_settings(user_settings_path)
    settings_path = _workspace_settings_path(workspace_path, filename='settings.json')
    workspace_data = _load_settings(settings_path)

    merged = _merged_settings(user_data, workspace_data)
    env_payload = _merged_env_payload(user_data, workspace_data)
    _apply_profile_env(env_payload, resolved_profile=resolved_profile)
    _assign_merged_env(merged, env_payload)

    if not merged:
        return None
    return save_json(settings_path, merged)


def trust_claude_workspace(*, workspace_path: Path) -> Path:
    trust_path = Path.home() / '.claude.json'
    data = _load_settings(trust_path)
    key = workspace_key(workspace_path)
    record = data.get(key)
    if not isinstance(record, dict):
        record = {}
    record['hasTrustDialogAccepted'] = True
    data[key] = record
    save_json(trust_path, data)
    return trust_path


def normalize_env_payload(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, str] = {}
    for key, item in value.items():
        if isinstance(key, str) and isinstance(item, str):
            result[key] = item
    return result


def claude_event_has_command(groups: list[object], command: str) -> bool:
    for group in groups:
        if not isinstance(group, dict):
            continue
        hooks = group.get('hooks')
        if not isinstance(hooks, list):
            continue
        for hook in hooks:
            if not isinstance(hook, dict):
                continue
            if str(hook.get('type') or '').strip().lower() != 'command':
                continue
            if str(hook.get('command') or '').strip() == command:
                return True
    return False


def _workspace_settings_path(workspace_path: Path, *, filename: str) -> Path:
    return Path(workspace_path).expanduser() / '.claude' / filename


def _load_settings(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return load_json(path)


def _hooks_payload(data: dict[str, Any]) -> dict[str, Any]:
    hooks = data.get('hooks')
    if not isinstance(hooks, dict):
        hooks = {}
    data['hooks'] = hooks
    return hooks


def _event_groups(hooks: dict[str, Any], *, event_name: str) -> list[object]:
    groups = hooks.get(event_name)
    if not isinstance(groups, list):
        return []
    return groups


def _command_hook_group(command: str) -> dict[str, list[dict[str, str]]]:
    return {
        'hooks': [
            {
                'type': 'command',
                'command': command,
            }
        ]
    }


def _merged_settings(*payloads: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for payload in payloads:
        if payload:
            merged.update(payload)
    return merged


def _merged_env_payload(*payloads: dict[str, Any]) -> dict[str, str]:
    env_payload: dict[str, str] = {}
    for payload in payloads:
        env_payload.update(normalize_env_payload(payload.get('env')))
    return env_payload


def _apply_profile_env(
    env_payload: dict[str, str],
    *,
    resolved_profile: ResolvedProviderProfile | None,
) -> None:
    if resolved_profile is None:
        return
    api_keys = provider_api_env_keys('claude')
    if not resolved_profile.inherit_api:
        for key in api_keys:
            env_payload.pop(key, None)
    for key, value in resolved_profile.env.items():
        if key in api_keys:
            env_payload[key] = value


def _assign_merged_env(merged: dict[str, Any], env_payload: dict[str, str]) -> None:
    if env_payload:
        merged['env'] = env_payload
        return
    merged.pop('env', None)


__all__ = [
    'install_claude_hooks',
    'sync_claude_workspace_settings',
    'trust_claude_workspace',
]
