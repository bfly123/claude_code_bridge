from __future__ import annotations

from pathlib import Path

from provider_profiles import ResolvedProviderProfile

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


def reconcile_claude_workspace_settings(
    *,
    workspace_path: Path,
    resolved_profile: ResolvedProviderProfile | None = None,
) -> Path | None:
    settings_path = _workspace_settings_path(workspace_path, filename='settings.json')
    del resolved_profile
    try:
        settings_path.unlink()
    except FileNotFoundError:
        pass
    return None


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


def _load_settings(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    return load_json(path)


def _hooks_payload(data: dict[str, object]) -> dict[str, object]:
    hooks = data.get('hooks')
    if not isinstance(hooks, dict):
        hooks = {}
    data['hooks'] = hooks
    return hooks


def _event_groups(hooks: dict[str, object], *, event_name: str) -> list[object]:
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


__all__ = [
    'install_claude_hooks',
    'reconcile_claude_workspace_settings',
    'trust_claude_workspace',
]
