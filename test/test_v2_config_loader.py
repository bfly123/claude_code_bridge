from __future__ import annotations

from pathlib import Path

import pytest

from agents.config_loader import (
    ConfigValidationError,
    build_default_project_config,
    ensure_bootstrap_project_config,
    ensure_default_project_config,
    load_project_config,
    render_default_project_config_text,
)
from agents.models import AgentSpec, PermissionMode, QueuePolicy, RestoreMode, RuntimeMode, WorkspaceMode
from agents.store import AgentSpecStore
from storage.paths import PathLayout


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def test_load_valid_project_config(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    config_path = project_root / '.ccb' / 'ccb.config'
    _write(config_path, 'cmd; agent1:codex\n')

    result = load_project_config(project_root)
    spec = result.config.agents['agent1']
    assert result.source_path == config_path
    assert spec.workspace_mode is WorkspaceMode.INPLACE
    assert spec.runtime_mode is RuntimeMode.PANE_BACKED
    assert spec.restore_default is RestoreMode.AUTO
    assert spec.permission_default is PermissionMode.MANUAL
    assert spec.queue_policy is QueuePolicy.SERIAL_PER_AGENT
    assert result.config.layout_spec == 'cmd; agent1:codex'


def test_load_project_config_rejects_provider_only_list(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    config_path = project_root / '.ccb' / 'ccb.config'
    _write(config_path, 'codex,claude,cmd\n')

    with pytest.raises(ConfigValidationError, match='expected'):
        load_project_config(project_root)


def test_load_project_config_supports_named_simple_agent_map(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    config_path = project_root / '.ccb' / 'ccb.config'
    _write(config_path, 'cmd, agent1:codex; agent2:codex, agent3:claude\n')

    result = load_project_config(project_root)

    assert result.source_path == config_path
    assert result.config.default_agents == ('agent1', 'agent2', 'agent3')
    assert set(result.config.agents) == {'agent1', 'agent2', 'agent3'}
    assert result.config.agents['agent1'].provider == 'codex'
    assert result.config.agents['agent2'].provider == 'codex'
    assert result.config.agents['agent3'].provider == 'claude'
    assert result.config.cmd_enabled is True
    assert result.config.layout_spec == 'cmd, agent1:codex; agent2:codex, agent3:claude'


def test_load_project_config_normalizes_mixed_case_compact_agent_names(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-mixed-case'
    config_path = project_root / '.ccb' / 'ccb.config'
    _write(
        config_path,
        'cmd, Alice:codex; Tomy:codex, Hanmeimei:claude; Lilei:gemini, Harry:gemini\n',
    )

    result = load_project_config(project_root)

    assert result.config.default_agents == ('alice', 'tomy', 'hanmeimei', 'lilei', 'harry')
    assert set(result.config.agents) == {'alice', 'tomy', 'hanmeimei', 'lilei', 'harry'}
    assert result.config.layout_spec == (
        'cmd, alice:codex; tomy:codex, hanmeimei:claude; lilei:gemini, harry:gemini'
    )


def test_load_project_config_rejects_case_insensitive_duplicates(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    config_path = project_root / '.ccb' / 'ccb.config'
    _write(config_path, 'Agent1:codex,agent1:claude\n')
    with pytest.raises(ConfigValidationError):
        load_project_config(project_root)


def test_build_and_ensure_default_project_config(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    config = build_default_project_config()
    assert config.default_agents == ('agent1', 'agent2', 'agent3')
    assert config.cmd_enabled is True
    written = ensure_default_project_config(project_root)
    assert written.exists()
    assert written.read_text(encoding='utf-8') == render_default_project_config_text()
    loaded = load_project_config(project_root)
    assert loaded.config.default_agents == ('agent1', 'agent2', 'agent3')
    assert loaded.config.cmd_enabled is True
    assert set(loaded.config.agents) == {'agent1', 'agent2', 'agent3'}
    assert loaded.config.agents['agent1'].provider == 'codex'
    assert loaded.config.agents['agent2'].provider == 'codex'
    assert loaded.config.agents['agent3'].provider == 'claude'
    assert loaded.config.agents['agent1'].workspace_mode is WorkspaceMode.INPLACE
    assert loaded.config.agents['agent1'].runtime_mode is RuntimeMode.PANE_BACKED


def test_ensure_bootstrap_project_config_allows_empty_anchor(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-empty-anchor'
    (project_root / '.ccb').mkdir(parents=True, exist_ok=True)

    written = ensure_bootstrap_project_config(project_root)

    assert written.exists()
    assert written.read_text(encoding='utf-8') == render_default_project_config_text()


def test_ensure_bootstrap_project_config_rejects_persisted_state_without_config(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-missing-config-with-state'
    runtime_path = project_root / '.ccb' / 'agents' / 'demo' / 'runtime.json'
    _write(runtime_path, '{"agent_name":"demo"}\n')

    with pytest.raises(ConfigValidationError, match='persisted state'):
        ensure_bootstrap_project_config(project_root)


def test_ensure_bootstrap_project_config_recovers_from_agent_specs(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-recover-config'
    layout = PathLayout(project_root)
    spec_store = AgentSpecStore(layout)
    for name, provider in (('agent1', 'codex'), ('agent2', 'codex'), ('agent3', 'claude')):
        spec_store.save(
            AgentSpec(
                name=name,
                provider=provider,
                target='.',
                workspace_mode=WorkspaceMode.INPLACE,
                workspace_root=None,
                runtime_mode=RuntimeMode.PANE_BACKED,
                restore_default=RestoreMode.AUTO,
                permission_default=PermissionMode.MANUAL,
                queue_policy=QueuePolicy.SERIAL_PER_AGENT,
            )
        )

    written = ensure_bootstrap_project_config(project_root)

    assert written.exists()
    assert written.read_text(encoding='utf-8') == 'cmd, agent1:codex; agent2:codex, agent3:claude\n'


def test_load_project_config_supports_explicit_worktree_suffix_in_compact_config(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-worktree-compact'
    config_path = project_root / '.ccb' / 'ccb.config'
    _write(config_path, 'cmd; agent1:codex(worktree), agent2:claude\n')

    result = load_project_config(project_root)

    assert result.config.agents['agent1'].workspace_mode is WorkspaceMode.GIT_WORKTREE
    assert result.config.agents['agent2'].workspace_mode is WorkspaceMode.INPLACE
    assert result.config.layout_spec == 'cmd; agent1:codex(worktree), agent2:claude'


def test_ensure_bootstrap_project_config_ignores_session_residue_for_default_bootstrap(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-session-residue'
    _write(project_root / '.ccb' / '.codex-agent1-session', '{}\n')
    _write(project_root / '.ccb' / '.claude-agent3-session', '{}\n')

    written = ensure_bootstrap_project_config(project_root)

    assert written.exists()
    assert written.read_text(encoding='utf-8') == render_default_project_config_text()


def test_load_project_config_rejects_invalid_token(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    config_path = project_root / '.ccb' / 'ccb.config'
    _write(config_path, 'demo\n')

    with pytest.raises(ConfigValidationError, match='expected'):
        load_project_config(project_root)


def test_reserved_agent_name_is_rejected(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    config_path = project_root / '.ccb' / 'ccb.config'
    _write(config_path, 'kill:codex\n')
    with pytest.raises(ConfigValidationError):
        load_project_config(project_root)


def test_cmd_only_config_is_rejected(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    config_path = project_root / '.ccb' / 'ccb.config'
    _write(config_path, 'cmd\n')
    with pytest.raises(ConfigValidationError, match='at least one agent'):
        load_project_config(project_root)


def test_cmd_cannot_be_used_as_agent_name(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    config_path = project_root / '.ccb' / 'ccb.config'
    _write(config_path, 'cmd:codex\n')
    with pytest.raises(ConfigValidationError, match='reserved token'):
        load_project_config(project_root)


def test_load_project_config_requires_project_local_file_even_when_home_has_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / 'home'
    global_config = home / '.ccb' / 'ccb.config'
    project_root = tmp_path / 'repo'
    project_root.mkdir()
    monkeypatch.setenv('HOME', str(home))
    _write(global_config, 'agent1:claude\n')

    with pytest.raises(ConfigValidationError, match='config not found'):
        load_project_config(project_root)



def test_load_project_config_supports_toml_provider_profile(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    config_path = project_root / '.ccb' / 'ccb.config'
    _write(
        config_path,
        """version = 2
default_agents = ["agent1"]
layout = "cmd; agent1"
cmd_enabled = true

[agents.agent1]
provider = "codex"
target = "."
workspace_mode = "git-worktree"
restore = "auto"
permission = "manual"

[agents.agent1.provider_profile]
mode = "isolated"
home = ".ccb/provider-profiles/agent1/codex"
inherit_api = false
inherit_auth = true
inherit_config = true
inherit_skills = false
inherit_commands = false

[agents.agent1.provider_profile.env]
OPENAI_API_KEY = "sk-test"
""",
    )

    result = load_project_config(project_root)
    spec = result.config.agents['agent1']

    assert spec.provider_profile.mode == 'isolated'
    assert spec.provider_profile.home == '.ccb/provider-profiles/agent1/codex'
    assert spec.provider_profile.inherit_api is False
    assert spec.provider_profile.inherit_auth is True
    assert spec.provider_profile.inherit_skills is False
    assert spec.provider_profile.inherit_commands is False
    assert spec.provider_profile.env == {'OPENAI_API_KEY': 'sk-test'}


def test_load_project_config_reads_project_ccb_config_path(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-layout-path'
    config_path = project_root / '.ccb' / 'ccb.config'
    _write(config_path, 'cmd; agent1:codex\n')

    result = load_project_config(project_root)

    assert result.source_path == config_path
    assert result.config.layout_spec == 'cmd; agent1:codex'
