from __future__ import annotations

import json
from pathlib import Path

from provider_hooks.settings import build_hook_command, install_workspace_completion_hooks


def test_build_hook_command_includes_completion_dir_and_workspace(tmp_path: Path) -> None:
    command = build_hook_command(
        provider='claude',
        script_path=tmp_path / 'bin' / 'ccb-provider-finish-hook',
        python_executable='/usr/bin/python3',
        completion_dir=tmp_path / 'completion',
        agent_name='agent1',
        workspace_path=tmp_path / 'workspace',
    )

    assert '--provider claude' in command
    assert '--agent-name agent1' in command
    assert '--completion-dir' in command
    assert '--workspace' in command


def test_install_claude_hooks_writes_managed_home_settings_only(tmp_path: Path) -> None:
    workspace = tmp_path / 'workspace'
    home_root = tmp_path / 'claude-home'
    command = '/usr/bin/python3 /tmp/ccb-provider-finish-hook --provider claude'

    settings_path = install_workspace_completion_hooks(
        provider='claude',
        workspace_path=workspace,
        home_root=home_root,
        command=command,
    )

    assert settings_path == home_root / '.claude' / 'settings.json'
    data = json.loads(settings_path.read_text(encoding='utf-8'))
    assert data['hooks']['Stop'][0]['hooks'][0]['command'] == command
    assert not (workspace / '.claude').exists()


def test_install_claude_hooks_preserves_existing_entries_without_duplication(tmp_path: Path) -> None:
    workspace = tmp_path / 'workspace'
    home_root = tmp_path / 'claude-home'
    settings_path = home_root / '.claude' / 'settings.json'
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    command = '/usr/bin/python3 /tmp/ccb-provider-finish-hook --provider claude'
    settings_path.write_text(
        json.dumps(
            {
                'hooks': {
                    'Stop': [
                        {'hooks': [{'type': 'command', 'command': 'echo existing'}]},
                        {'hooks': [{'type': 'command', 'command': command}]},
                    ]
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding='utf-8',
    )

    install_workspace_completion_hooks(
        provider='claude',
        workspace_path=workspace,
        home_root=home_root,
        command=command,
    )

    data = json.loads(settings_path.read_text(encoding='utf-8'))
    assert len(data['hooks']['Stop']) == 2
    assert not (workspace / '.claude').exists()


def test_install_claude_hooks_trusts_workspace_in_managed_home(tmp_path: Path) -> None:
    workspace = tmp_path / 'workspace'
    home_root = tmp_path / 'claude-home'
    command = '/usr/bin/python3 /tmp/ccb-provider-finish-hook --provider claude'

    install_workspace_completion_hooks(
        provider='claude',
        workspace_path=workspace,
        home_root=home_root,
        command=command,
    )

    trust_path = home_root / '.claude.json'
    trust_data = json.loads(trust_path.read_text(encoding='utf-8'))
    assert trust_data[str(workspace.resolve())]['hasTrustDialogAccepted'] is True
    assert not (workspace / '.claude').exists()


def test_install_gemini_hooks_writes_managed_home_settings_only(tmp_path: Path) -> None:
    workspace = tmp_path / 'workspace'
    home_root = tmp_path / 'gemini-home'
    command = '/usr/bin/python3 /tmp/ccb-provider-finish-hook --provider gemini'

    settings_path = install_workspace_completion_hooks(
        provider='gemini',
        workspace_path=workspace,
        home_root=home_root,
        command=command,
    )

    assert settings_path == home_root / '.gemini' / 'settings.json'
    data = json.loads(settings_path.read_text(encoding='utf-8'))
    assert data['hooks']['AfterAgent'][0]['matcher'] == '*'
    assert data['hooks']['AfterAgent'][0]['hooks'][0]['command'] == command
    assert not (workspace / '.gemini').exists()


def test_install_gemini_hooks_trusts_workspace_in_managed_home(tmp_path: Path) -> None:
    workspace = tmp_path / 'workspace'
    home_root = tmp_path / 'gemini-home'
    command = '/usr/bin/python3 /tmp/ccb-provider-finish-hook --provider gemini'

    install_workspace_completion_hooks(
        provider='gemini',
        workspace_path=workspace,
        home_root=home_root,
        command=command,
    )

    trust_path = home_root / '.gemini' / 'trustedFolders.json'
    data = json.loads(trust_path.read_text(encoding='utf-8'))
    assert data[str(workspace.resolve())] == 'TRUST_FOLDER'
    assert not (workspace / '.gemini').exists()
