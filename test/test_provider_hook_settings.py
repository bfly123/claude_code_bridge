from __future__ import annotations

import json
from pathlib import Path

from provider_hooks.settings import build_hook_command, install_workspace_completion_hooks
from provider_profiles.models import ResolvedProviderProfile


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


def test_install_claude_hooks_writes_settings_local_json(tmp_path: Path) -> None:
    workspace = tmp_path / 'workspace'
    command = '/usr/bin/python3 /tmp/ccb-provider-finish-hook --provider claude'

    settings_path = install_workspace_completion_hooks(
        provider='claude',
        workspace_path=workspace,
        command=command,
    )

    assert settings_path == workspace / '.claude' / 'settings.local.json'
    data = json.loads(settings_path.read_text(encoding='utf-8'))
    assert data['hooks']['Stop'][0]['hooks'][0]['command'] == command
    assert 'StopFailure' not in data['hooks']


def test_install_claude_hooks_preserves_existing_entries_without_duplication(tmp_path: Path) -> None:
    workspace = tmp_path / 'workspace'
    settings_path = workspace / '.claude' / 'settings.local.json'
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
        command=command,
    )

    data = json.loads(settings_path.read_text(encoding='utf-8'))
    assert len(data['hooks']['Stop']) == 2
    assert 'StopFailure' not in data['hooks']


def test_install_claude_hooks_syncs_user_settings_and_trusts_workspace(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / 'home'
    workspace = tmp_path / 'workspace'
    command = '/usr/bin/python3 /tmp/ccb-provider-finish-hook --provider claude'
    monkeypatch.setenv('HOME', str(home))

    user_settings_path = home / '.claude' / 'settings.json'
    user_settings_path.parent.mkdir(parents=True, exist_ok=True)
    user_settings_path.write_text(
        json.dumps(
            {
                'env': {
                    'ANTHROPIC_AUTH_TOKEN': 'token-1',
                    'ANTHROPIC_BASE_URL': 'https://example.invalid/claude',
                },
                'theme': 'system',
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding='utf-8',
    )

    install_workspace_completion_hooks(
        provider='claude',
        workspace_path=workspace,
        command=command,
    )

    settings_path = workspace / '.claude' / 'settings.json'
    settings = json.loads(settings_path.read_text(encoding='utf-8'))
    assert settings['env']['ANTHROPIC_AUTH_TOKEN'] == 'token-1'
    assert settings['env']['ANTHROPIC_BASE_URL'] == 'https://example.invalid/claude'
    assert settings['theme'] == 'system'

    trust_path = home / '.claude.json'
    trust_data = json.loads(trust_path.read_text(encoding='utf-8'))
    assert trust_data[str(workspace.resolve())]['hasTrustDialogAccepted'] is True


def test_install_gemini_hooks_writes_settings_json(tmp_path: Path) -> None:
    workspace = tmp_path / 'workspace'
    command = '/usr/bin/python3 /tmp/ccb-provider-finish-hook --provider gemini'

    settings_path = install_workspace_completion_hooks(
        provider='gemini',
        workspace_path=workspace,
        command=command,
    )

    assert settings_path == workspace / '.gemini' / 'settings.json'
    data = json.loads(settings_path.read_text(encoding='utf-8'))
    assert data['hooks']['AfterAgent'][0]['matcher'] == '*'
    assert data['hooks']['AfterAgent'][0]['hooks'][0]['command'] == command


def test_install_gemini_hooks_trusts_workspace(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / 'home'
    workspace = tmp_path / 'workspace'
    command = '/usr/bin/python3 /tmp/ccb-provider-finish-hook --provider gemini'
    monkeypatch.setenv('HOME', str(home))

    install_workspace_completion_hooks(
        provider='gemini',
        workspace_path=workspace,
        command=command,
    )

    trust_path = home / '.gemini' / 'trustedFolders.json'
    data = json.loads(trust_path.read_text(encoding='utf-8'))
    assert data[str(workspace.resolve())] == 'TRUST_FOLDER'



def test_install_claude_hooks_strips_system_api_env_for_isolated_profile(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / 'home'
    workspace = tmp_path / 'workspace'
    command = '/usr/bin/python3 /tmp/ccb-provider-finish-hook --provider claude'
    monkeypatch.setenv('HOME', str(home))

    user_settings_path = home / '.claude' / 'settings.json'
    user_settings_path.parent.mkdir(parents=True, exist_ok=True)
    user_settings_path.write_text(
        json.dumps(
            {
                'env': {
                    'ANTHROPIC_AUTH_TOKEN': 'token-1',
                    'ANTHROPIC_BASE_URL': 'https://example.invalid/claude',
                    'FOO': 'bar',
                },
                'theme': 'system',
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding='utf-8',
    )

    install_workspace_completion_hooks(
        provider='claude',
        workspace_path=workspace,
        command=command,
        resolved_profile=ResolvedProviderProfile(
            provider='claude',
            agent_name='agent1',
            mode='isolated',
            profile_root=str(tmp_path / 'profile'),
            runtime_home=None,
            env={'ANTHROPIC_API_KEY': 'api-2'},
            inherit_api=False,
        ),
    )

    settings_path = workspace / '.claude' / 'settings.json'
    settings = json.loads(settings_path.read_text(encoding='utf-8'))
    assert settings['env']['ANTHROPIC_API_KEY'] == 'api-2'
    assert settings['env']['FOO'] == 'bar'
    assert 'ANTHROPIC_AUTH_TOKEN' not in settings['env']
    assert 'ANTHROPIC_BASE_URL' not in settings['env']
    assert settings['theme'] == 'system'
