from __future__ import annotations

import json
from pathlib import Path
import shlex
from typing import Any

from provider_profiles import ResolvedProviderProfile, provider_api_env_keys
from storage.atomic import atomic_write_json


def build_hook_command(
    *,
    provider: str,
    script_path: Path,
    python_executable: str,
    completion_dir: Path,
    agent_name: str,
    workspace_path: Path,
) -> str:
    parts = [
        python_executable,
        str(Path(script_path).expanduser()),
        '--provider',
        str(provider),
        '--completion-dir',
        str(Path(completion_dir).expanduser()),
        '--agent-name',
        str(agent_name),
        '--workspace',
        str(Path(workspace_path).expanduser()),
    ]
    return ' '.join(shlex.quote(str(part)) for part in parts)


def install_workspace_completion_hooks(
    *,
    provider: str,
    workspace_path: Path,
    command: str,
    resolved_profile: ResolvedProviderProfile | None = None,
) -> Path | None:
    normalized = str(provider or '').strip().lower()
    if normalized == 'claude':
        settings_path = _install_claude_hooks(workspace_path=workspace_path, command=command)
        _sync_claude_workspace_settings(workspace_path=workspace_path, resolved_profile=resolved_profile)
        _trust_claude_workspace(workspace_path=workspace_path)
        return settings_path
    if normalized == 'gemini':
        settings_path = _install_gemini_hooks(workspace_path=workspace_path, command=command)
        _trust_gemini_workspace(workspace_path=workspace_path)
        return settings_path
    return None


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}
    return dict(data) if isinstance(data, dict) else {}


def _save_json(path: Path, payload: dict[str, Any]) -> Path:
    atomic_write_json(path, payload)
    return path


def _install_claude_hooks(*, workspace_path: Path, command: str) -> Path:
    settings_path = Path(workspace_path).expanduser() / '.claude' / 'settings.local.json'
    data = _load_json(settings_path) if settings_path.exists() else {}
    hooks = data.get('hooks')
    if not isinstance(hooks, dict):
        hooks = {}
    data['hooks'] = hooks

    for event_name in ('Stop',):
        groups = hooks.get(event_name)
        if not isinstance(groups, list):
            groups = []
        if not _claude_event_has_command(groups, command):
            groups.append(
                {
                    'hooks': [
                        {
                            'type': 'command',
                            'command': command,
                        }
                    ]
                }
            )
        hooks[event_name] = groups

    return _save_json(settings_path, data)


def _sync_claude_workspace_settings(
    *,
    workspace_path: Path,
    resolved_profile: ResolvedProviderProfile | None = None,
) -> Path | None:
    user_settings_path = Path.home() / '.claude' / 'settings.json'
    user_data = _load_json(user_settings_path) if user_settings_path.exists() else {}

    settings_path = Path(workspace_path).expanduser() / '.claude' / 'settings.json'
    workspace_data = _load_json(settings_path) if settings_path.exists() else {}

    merged: dict[str, Any] = {}
    if user_data:
        merged.update(user_data)
    if workspace_data:
        merged.update(workspace_data)

    env_payload = _normalize_env_payload(user_data.get('env'))
    env_payload.update(_normalize_env_payload(workspace_data.get('env')))

    api_keys = provider_api_env_keys('claude')
    if resolved_profile is not None and not resolved_profile.inherit_api:
        for key in api_keys:
            env_payload.pop(key, None)
    if resolved_profile is not None:
        for key, value in resolved_profile.env.items():
            if key in api_keys:
                env_payload[key] = value

    if env_payload:
        merged['env'] = env_payload
    else:
        merged.pop('env', None)

    if not merged:
        return None
    return _save_json(settings_path, merged)


def _normalize_env_payload(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, str] = {}
    for key, item in value.items():
        if isinstance(key, str) and isinstance(item, str):
            result[key] = item
    return result


def _trust_claude_workspace(*, workspace_path: Path) -> Path:
    trust_path = Path.home() / '.claude.json'
    data = _load_json(trust_path) if trust_path.exists() else {}
    try:
        workspace_key = str(Path(workspace_path).expanduser().resolve())
    except Exception:
        workspace_key = str(Path(workspace_path).expanduser())
    record = data.get(workspace_key)
    if not isinstance(record, dict):
        record = {}
    record['hasTrustDialogAccepted'] = True
    data[workspace_key] = record
    atomic_write_json(trust_path, data)
    return trust_path


def _claude_event_has_command(groups: list[object], command: str) -> bool:
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


def _install_gemini_hooks(*, workspace_path: Path, command: str) -> Path:
    settings_path = Path(workspace_path).expanduser() / '.gemini' / 'settings.json'
    data = _load_json(settings_path) if settings_path.exists() else {}
    hooks = data.get('hooks')
    if not isinstance(hooks, dict):
        hooks = {}
    data['hooks'] = hooks

    after_agent = hooks.get('AfterAgent')
    if not isinstance(after_agent, list):
        after_agent = []
    if not _gemini_event_has_command(after_agent, command):
        after_agent.append(
            {
                'matcher': '*',
                'hooks': [
                    {
                        'type': 'command',
                        'command': command,
                    }
                ],
            }
        )
    hooks['AfterAgent'] = after_agent
    return _save_json(settings_path, data)


def _gemini_event_has_command(groups: list[object], command: str) -> bool:
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


def _trust_gemini_workspace(*, workspace_path: Path) -> Path:
    trust_path = Path.home() / '.gemini' / 'trustedFolders.json'
    data = _load_json(trust_path) if trust_path.exists() else {}
    try:
        workspace_key = str(Path(workspace_path).expanduser().resolve())
    except Exception:
        workspace_key = str(Path(workspace_path).expanduser())
    data[workspace_key] = 'TRUST_FOLDER'
    atomic_write_json(trust_path, data)
    return trust_path
