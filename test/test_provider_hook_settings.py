from __future__ import annotations

import json
from pathlib import Path

from agents.models import AgentSpec, PermissionMode, ProviderProfileSpec, QueuePolicy, RestoreMode, RuntimeMode, WorkspaceMode
from cli.services.provider_hooks import prepare_provider_workspace
from provider_hooks.settings import build_hook_command, install_workspace_completion_hooks
from storage.paths import PathLayout


def _spec(name: str, provider: str = "claude", *, provider_profile: ProviderProfileSpec | None = None) -> AgentSpec:
    return AgentSpec(
        name=name,
        provider=provider,
        target='.',
        workspace_mode=WorkspaceMode.GIT_WORKTREE,
        workspace_root=None,
        runtime_mode=RuntimeMode.PANE_BACKED,
        restore_default=RestoreMode.AUTO,
        permission_default=PermissionMode.MANUAL,
        queue_policy=QueuePolicy.SERIAL_PER_AGENT,
        provider_profile=provider_profile or ProviderProfileSpec(),
    )


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


def test_prepare_provider_workspace_materializes_claude_settings_before_hooks(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo'
    workspace = project_root / 'workspace'
    system_home = tmp_path / 'system-home'
    system_settings = system_home / '.claude' / 'settings.json'
    system_settings.parent.mkdir(parents=True, exist_ok=True)
    system_settings.write_text(
        json.dumps(
            {
                'env': {
                    'ANTHROPIC_AUTH_TOKEN': 'system-token',
                    'ANTHROPIC_BASE_URL': 'https://claude.example.test',
                },
                'theme': 'light',
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding='utf-8',
    )
    monkeypatch.setenv('HOME', str(system_home))

    prepare_provider_workspace(
        layout=PathLayout(project_root),
        spec=_spec('agent1'),
        workspace_path=workspace,
        completion_dir=project_root / '.ccb' / 'agents' / 'agent1' / 'provider-runtime' / 'claude' / 'completion',
        agent_name='agent1',
        refresh_profile=True,
    )

    settings_path = project_root / '.ccb' / 'agents' / 'agent1' / 'provider-state' / 'claude' / 'home' / '.claude' / 'settings.json'
    payload = json.loads(settings_path.read_text(encoding='utf-8'))
    assert payload['env']['ANTHROPIC_AUTH_TOKEN'] == 'system-token'
    assert payload['env']['ANTHROPIC_BASE_URL'] == 'https://claude.example.test'
    assert payload['theme'] == 'light'
    assert payload['hooks']['Stop'][0]['hooks'][0]['command']
    assert not (workspace / '.claude').exists()


def test_prepare_provider_workspace_repairs_existing_claude_hook_only_settings(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo'
    workspace = project_root / 'workspace'
    system_home = tmp_path / 'system-home'
    system_settings = system_home / '.claude' / 'settings.json'
    system_settings.parent.mkdir(parents=True, exist_ok=True)
    system_settings.write_text(
        json.dumps(
            {
                'env': {'ANTHROPIC_AUTH_TOKEN': 'system-token'},
                'theme': 'dark',
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding='utf-8',
    )
    monkeypatch.setenv('HOME', str(system_home))

    managed_settings = project_root / '.ccb' / 'agents' / 'agent1' / 'provider-state' / 'claude' / 'home' / '.claude' / 'settings.json'
    managed_settings.parent.mkdir(parents=True, exist_ok=True)
    managed_settings.write_text(
        json.dumps(
            {
                'hooks': {
                    'Stop': [
                        {
                            'hooks': [
                                {
                                    'type': 'command',
                                    'command': 'echo legacy-hook',
                                }
                            ]
                        }
                    ]
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding='utf-8',
    )

    prepare_provider_workspace(
        layout=PathLayout(project_root),
        spec=_spec('agent1'),
        workspace_path=workspace,
        completion_dir=project_root / '.ccb' / 'agents' / 'agent1' / 'provider-runtime' / 'claude' / 'completion',
        agent_name='agent1',
        refresh_profile=True,
    )

    payload = json.loads(managed_settings.read_text(encoding='utf-8'))
    assert payload['env']['ANTHROPIC_AUTH_TOKEN'] == 'system-token'
    assert payload['theme'] == 'dark'
    commands = [hook['command'] for group in payload['hooks']['Stop'] for hook in group.get('hooks', []) if isinstance(hook, dict)]
    assert 'echo legacy-hook' in commands


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


def test_prepare_provider_workspace_materializes_gemini_settings_before_hooks(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo'
    workspace = project_root / 'workspace'
    system_home = tmp_path / 'system-home'
    system_settings = system_home / '.gemini' / 'settings.json'
    system_settings.parent.mkdir(parents=True, exist_ok=True)
    system_settings.write_text(
        json.dumps(
            {
                'env': {
                    'GEMINI_API_KEY': 'system-gemini-key',
                    'GOOGLE_API_KEY': 'system-google-key',
                },
                'theme': 'Default',
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding='utf-8',
    )
    monkeypatch.setenv('HOME', str(system_home))

    prepare_provider_workspace(
        layout=PathLayout(project_root),
        spec=_spec('agent1', provider='gemini'),
        workspace_path=workspace,
        completion_dir=project_root / '.ccb' / 'agents' / 'agent1' / 'provider-runtime' / 'gemini' / 'completion',
        agent_name='agent1',
        refresh_profile=True,
    )

    settings_path = project_root / '.ccb' / 'agents' / 'agent1' / 'provider-state' / 'gemini' / 'home' / '.gemini' / 'settings.json'
    payload = json.loads(settings_path.read_text(encoding='utf-8'))
    assert payload['env']['GEMINI_API_KEY'] == 'system-gemini-key'
    assert payload['env']['GOOGLE_API_KEY'] == 'system-google-key'
    assert payload['theme'] == 'Default'
    assert payload['hooks']['AfterAgent'][0]['hooks'][0]['command']
    assert not (workspace / '.gemini').exists()


def test_prepare_provider_workspace_repairs_existing_gemini_hook_only_settings(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo'
    workspace = project_root / 'workspace'
    system_home = tmp_path / 'system-home'
    system_settings = system_home / '.gemini' / 'settings.json'
    system_settings.parent.mkdir(parents=True, exist_ok=True)
    system_settings.write_text(
        json.dumps(
            {
                'env': {'GEMINI_API_KEY': 'system-gemini-key'},
                'theme': 'Atom One',
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding='utf-8',
    )
    monkeypatch.setenv('HOME', str(system_home))

    managed_settings = project_root / '.ccb' / 'agents' / 'agent1' / 'provider-state' / 'gemini' / 'home' / '.gemini' / 'settings.json'
    managed_settings.parent.mkdir(parents=True, exist_ok=True)
    managed_settings.write_text(
        json.dumps(
            {
                'hooks': {
                    'AfterAgent': [
                        {
                            'matcher': '*',
                            'hooks': [
                                {
                                    'type': 'command',
                                    'command': 'echo legacy-gemini-hook',
                                }
                            ],
                        }
                    ]
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding='utf-8',
    )

    prepare_provider_workspace(
        layout=PathLayout(project_root),
        spec=_spec('agent1', provider='gemini'),
        workspace_path=workspace,
        completion_dir=project_root / '.ccb' / 'agents' / 'agent1' / 'provider-runtime' / 'gemini' / 'completion',
        agent_name='agent1',
        refresh_profile=True,
    )

    payload = json.loads(managed_settings.read_text(encoding='utf-8'))
    assert payload['env']['GEMINI_API_KEY'] == 'system-gemini-key'
    assert payload['theme'] == 'Atom One'
    commands = [hook['command'] for group in payload['hooks']['AfterAgent'] for hook in group.get('hooks', []) if isinstance(hook, dict)]
    assert 'echo legacy-gemini-hook' in commands


def test_prepare_provider_workspace_merges_gemini_trusted_folders(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo'
    workspace = project_root / 'workspace'
    system_home = tmp_path / 'system-home'
    system_trust = system_home / '.gemini' / 'trustedFolders.json'
    system_trust.parent.mkdir(parents=True, exist_ok=True)
    system_trust.write_text(
        json.dumps({'/system/project': 'TRUST_FOLDER'}, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    managed_trust = project_root / '.ccb' / 'agents' / 'agent1' / 'provider-state' / 'gemini' / 'home' / '.gemini' / 'trustedFolders.json'
    managed_trust.parent.mkdir(parents=True, exist_ok=True)
    managed_trust.write_text(
        json.dumps({'/managed/project': 'TRUST_FOLDER'}, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    monkeypatch.setenv('HOME', str(system_home))

    prepare_provider_workspace(
        layout=PathLayout(project_root),
        spec=_spec('agent1', provider='gemini'),
        workspace_path=workspace,
        completion_dir=project_root / '.ccb' / 'agents' / 'agent1' / 'provider-runtime' / 'gemini' / 'completion',
        agent_name='agent1',
        refresh_profile=True,
    )

    payload = json.loads(managed_trust.read_text(encoding='utf-8'))
    assert payload['/system/project'] == 'TRUST_FOLDER'
    assert payload['/managed/project'] == 'TRUST_FOLDER'
    assert payload[str(workspace.resolve())] == 'TRUST_FOLDER'
