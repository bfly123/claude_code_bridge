from __future__ import annotations

from pathlib import Path

from .common import load_json, save_json, workspace_key


def install_gemini_hooks(*, home_root: Path, command: str) -> Path:
    settings_path = _gemini_settings_path(home_root)
    data = load_json(settings_path) if settings_path.exists() else {}
    hooks = data.get('hooks')
    if not isinstance(hooks, dict):
        hooks = {}
    data['hooks'] = hooks

    after_agent = hooks.get('AfterAgent')
    if not isinstance(after_agent, list):
        after_agent = []
    if not gemini_event_has_command(after_agent, command):
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
    return save_json(settings_path, data)


def trust_gemini_workspace(*, home_root: Path, workspace_path: Path) -> Path:
    trust_path = _trusted_folders_path(home_root)
    data = load_json(trust_path) if trust_path.exists() else {}
    data[workspace_key(workspace_path)] = 'TRUST_FOLDER'
    save_json(trust_path, data)
    return trust_path


def gemini_event_has_command(groups: list[object], command: str) -> bool:
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


def _gemini_settings_path(home_root: Path) -> Path:
    return Path(home_root).expanduser() / '.gemini' / 'settings.json'


def _trusted_folders_path(home_root: Path) -> Path:
    return Path(home_root).expanduser() / '.gemini' / 'trustedFolders.json'


__all__ = ['install_gemini_hooks', 'trust_gemini_workspace']
