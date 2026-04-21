from __future__ import annotations

import json
from pathlib import Path

from agents.models import AgentSpec, PermissionMode, ProviderProfileSpec, QueuePolicy, RestoreMode, RuntimeMode, WorkspaceMode
from provider_backends.claude.launcher_runtime.home import materialize_claude_home_config
from provider_backends.gemini.launcher_runtime.home import materialize_gemini_home_config
from provider_profiles import materialize_provider_profile
from storage.paths import PathLayout


def _spec(name: str, provider: str = "codex", *, provider_profile: ProviderProfileSpec | None = None) -> AgentSpec:
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


def test_materialize_codex_profile_copies_inherited_assets(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'repo'
    source_home = tmp_path / 'system-codex-home'
    (source_home / 'skills').mkdir(parents=True, exist_ok=True)
    (source_home / 'commands').mkdir(parents=True, exist_ok=True)
    (source_home / 'config.toml').write_text('model = "gpt-5"\n', encoding='utf-8')
    (source_home / 'auth.json').write_text('{"OPENAI_API_KEY":"system-key"}', encoding='utf-8')
    (source_home / 'skills' / 'demo.md').write_text('demo skill\n', encoding='utf-8')
    (source_home / 'commands' / 'demo.md').write_text('demo command\n', encoding='utf-8')
    monkeypatch.setenv('CODEX_HOME', str(source_home))

    profile = materialize_provider_profile(
        layout=PathLayout(project_root),
        spec=_spec(
            'agent1',
            provider_profile=ProviderProfileSpec(
                mode='isolated',
                inherit_api=False,
                inherit_auth=True,
                inherit_config=True,
                inherit_skills=True,
                inherit_commands=True,
            ),
        ),
        workspace_path=project_root,
    )

    runtime_home = Path(profile.runtime_home or '')
    assert runtime_home.is_dir()
    assert (runtime_home / 'config.toml').is_file()
    assert (runtime_home / 'auth.json').is_file()
    assert (runtime_home / 'skills' / 'demo.md').is_file()
    assert (runtime_home / 'commands' / 'demo.md').is_file()
    assert (runtime_home / 'sessions').is_dir()


def test_materialize_claude_profile_creates_runtime_home(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'

    profile = materialize_provider_profile(
        layout=PathLayout(project_root),
        spec=_spec(
            'agent1',
            provider='claude',
            provider_profile=ProviderProfileSpec(
                mode='isolated',
                inherit_api=False,
            ),
        ),
        workspace_path=project_root,
    )

    runtime_home = Path(profile.runtime_home or '')
    assert runtime_home.is_dir()


def test_materialize_claude_home_config_projects_system_settings_into_managed_home(tmp_path: Path) -> None:
    source_home = tmp_path / 'system-home'
    target_home = tmp_path / 'managed-home'
    source_settings = source_home / '.claude' / 'settings.json'
    source_settings.parent.mkdir(parents=True, exist_ok=True)
    source_settings.write_text(
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

    layout = materialize_claude_home_config(target_home, source_home=source_home)

    payload = json.loads(layout.settings_path.read_text(encoding='utf-8'))
    assert payload['env']['ANTHROPIC_AUTH_TOKEN'] == 'system-token'
    assert payload['env']['ANTHROPIC_BASE_URL'] == 'https://claude.example.test'
    assert payload['theme'] == 'light'


def test_materialize_claude_home_config_preserves_runtime_hooks_and_permissions(tmp_path: Path) -> None:
    source_home = tmp_path / 'system-home'
    target_home = tmp_path / 'managed-home'
    source_settings = source_home / '.claude' / 'settings.json'
    source_settings.parent.mkdir(parents=True, exist_ok=True)
    source_settings.write_text(
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
    target_settings = target_home / '.claude' / 'settings.json'
    target_settings.parent.mkdir(parents=True, exist_ok=True)
    target_settings.write_text(
        json.dumps(
            {
                'hooks': {'Stop': [{'hooks': [{'type': 'command', 'command': 'echo hook'}]}]},
                'permissions': {'allow': ['Bash(ls)']},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding='utf-8',
    )

    layout = materialize_claude_home_config(target_home, source_home=source_home)

    payload = json.loads(layout.settings_path.read_text(encoding='utf-8'))
    assert payload['env']['ANTHROPIC_AUTH_TOKEN'] == 'system-token'
    assert payload['theme'] == 'dark'
    assert payload['hooks']['Stop'][0]['hooks'][0]['command'] == 'echo hook'
    assert payload['permissions']['allow'] == ['Bash(ls)']


def test_materialize_gemini_profile_keeps_runtime_home_unset_without_explicit_override(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'

    profile = materialize_provider_profile(
        layout=PathLayout(project_root),
        spec=_spec(
            'agent1',
            provider='gemini',
            provider_profile=ProviderProfileSpec(
                mode='isolated',
                inherit_api=False,
            ),
        ),
        workspace_path=project_root,
    )

    assert profile.runtime_home is None


def test_materialize_gemini_profile_uses_explicit_home_override(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    explicit_home = tmp_path / 'gemini-home'

    profile = materialize_provider_profile(
        layout=PathLayout(project_root),
        spec=_spec(
            'agent1',
            provider='gemini',
            provider_profile=ProviderProfileSpec(
                mode='isolated',
                home=str(explicit_home),
                inherit_api=False,
            ),
        ),
        workspace_path=project_root,
    )

    runtime_home = Path(profile.runtime_home or '')
    assert runtime_home == explicit_home.resolve()
    assert (runtime_home / '.gemini' / 'tmp').is_dir()


def test_materialize_gemini_home_config_projects_system_settings_into_managed_home(tmp_path: Path) -> None:
    source_home = tmp_path / 'system-home'
    target_home = tmp_path / 'managed-home'
    source_settings = source_home / '.gemini' / 'settings.json'
    source_settings.parent.mkdir(parents=True, exist_ok=True)
    source_settings.write_text(
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

    layout = materialize_gemini_home_config(target_home, source_home=source_home)

    payload = json.loads(layout.settings_path.read_text(encoding='utf-8'))
    assert payload['env']['GEMINI_API_KEY'] == 'system-gemini-key'
    assert payload['env']['GOOGLE_API_KEY'] == 'system-google-key'
    assert payload['theme'] == 'Default'


def test_materialize_gemini_home_config_preserves_runtime_hooks(tmp_path: Path) -> None:
    source_home = tmp_path / 'system-home'
    target_home = tmp_path / 'managed-home'
    source_settings = source_home / '.gemini' / 'settings.json'
    source_settings.parent.mkdir(parents=True, exist_ok=True)
    source_settings.write_text(
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
    target_settings = target_home / '.gemini' / 'settings.json'
    target_settings.parent.mkdir(parents=True, exist_ok=True)
    target_settings.write_text(
        json.dumps(
            {
                'hooks': {
                    'AfterAgent': [
                        {'matcher': '*', 'hooks': [{'type': 'command', 'command': 'echo hook'}]},
                    ]
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding='utf-8',
    )

    layout = materialize_gemini_home_config(target_home, source_home=source_home)

    payload = json.loads(layout.settings_path.read_text(encoding='utf-8'))
    assert payload['env']['GEMINI_API_KEY'] == 'system-gemini-key'
    assert payload['theme'] == 'Atom One'
    assert payload['hooks']['AfterAgent'][0]['hooks'][0]['command'] == 'echo hook'


def test_materialize_gemini_home_config_merges_trusted_folders(tmp_path: Path) -> None:
    source_home = tmp_path / 'system-home'
    target_home = tmp_path / 'managed-home'
    source_trust = source_home / '.gemini' / 'trustedFolders.json'
    source_trust.parent.mkdir(parents=True, exist_ok=True)
    source_trust.write_text(
        json.dumps({'/system/project': 'TRUST_FOLDER'}, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    target_trust = target_home / '.gemini' / 'trustedFolders.json'
    target_trust.parent.mkdir(parents=True, exist_ok=True)
    target_trust.write_text(
        json.dumps({'/managed/project': 'TRUST_FOLDER'}, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )

    layout = materialize_gemini_home_config(target_home, source_home=source_home)

    payload = json.loads(layout.trusted_folders_path.read_text(encoding='utf-8'))
    assert payload['/system/project'] == 'TRUST_FOLDER'
    assert payload['/managed/project'] == 'TRUST_FOLDER'
