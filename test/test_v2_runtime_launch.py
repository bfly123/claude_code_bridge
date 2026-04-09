from __future__ import annotations

import json
from pathlib import Path
import shlex
import subprocess
import pytest

from agents.models import (
    AgentSpec,
    PermissionMode,
    QueuePolicy,
    RestoreMode,
    RuntimeMode,
    WorkspaceMode,
)
from cli.context import CliContext
from cli.models import ParsedStartCommand
from cli.services.provider_binding import AgentBinding
import cli.services.runtime_launch as runtime_launch
from cli.services.runtime_launch import ensure_agent_runtime
from provider_backends.claude import launcher as claude_launcher
from provider_backends.codex import launcher as codex_launcher
from provider_backends.gemini import launcher as gemini_launcher
from provider_backends.runtime_restore import ProviderRestoreTarget
from provider_profiles.models import ResolvedProviderProfile
from project.ids import compute_project_id
from project.resolver import ProjectContext
from storage.paths import PathLayout
from terminal_runtime.tmux_identity import pane_visual
from workspace.planner import WorkspacePlanner


def _spec(name: str, provider: str = 'codex') -> AgentSpec:
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
    )


def _context(project_root: Path, command: ParsedStartCommand) -> CliContext:
    project_root = project_root.resolve()
    config_dir = project_root / '.ccb'
    config_dir.mkdir(parents=True, exist_ok=True)
    project = ProjectContext(
        cwd=project_root,
        project_root=project_root,
        config_dir=config_dir,
        project_id=compute_project_id(project_root),
        source='test',
    )
    return CliContext(command=command, cwd=project_root, project=project, paths=PathLayout(project_root))


def _write_provider_profile(runtime_dir: Path, profile: ResolvedProviderProfile) -> None:
    runtime_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / 'provider-profile.json').write_text(
        json.dumps(profile.to_record(), ensure_ascii=False, indent=2),
        encoding='utf-8',
    )


def test_ensure_agent_runtime_reconciles_claude_workspace_before_launch(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-claude-hooks'
    home = tmp_path / 'home'
    (project_root / '.ccb').mkdir(parents=True)
    monkeypatch.setenv('HOME', str(home))
    user_settings_path = home / '.claude' / 'settings.json'
    user_settings_path.parent.mkdir(parents=True, exist_ok=True)
    user_settings_path.write_text(
        json.dumps(
            {
                'env': {
                    'ANTHROPIC_AUTH_TOKEN': 'token-system',
                    'ANTHROPIC_BASE_URL': 'https://api.system.invalid',
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding='utf-8',
    )

    ctx = _context(project_root, ParsedStartCommand(project=None, agent_names=('agent3',), restore=False, auto_permission=False))
    spec = _spec('agent3', provider='claude')
    plan = WorkspacePlanner().plan(spec, ctx.project)
    workspace_settings = plan.workspace_path / '.claude' / 'settings.json'
    workspace_settings.parent.mkdir(parents=True, exist_ok=True)
    workspace_settings.write_text(
        json.dumps(
            {
                'env': {
                    'ANTHROPIC_AUTH_TOKEN': 'token-stale',
                    'ANTHROPIC_BASE_URL': 'https://api.stale.invalid',
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding='utf-8',
    )

    observed: dict[str, object] = {}

    def fake_ensure_impl(*args, **kwargs):
        del args, kwargs
        observed['workspace_settings_exists'] = workspace_settings.exists()
        return runtime_launch.RuntimeLaunchResult(launched=False, binding=None)

    monkeypatch.setattr(runtime_launch, '_ensure_agent_runtime_impl', fake_ensure_impl)

    result = ensure_agent_runtime(ctx, ctx.command, spec, plan, None)

    assert result == runtime_launch.RuntimeLaunchResult(launched=False, binding=None)
    assert observed['workspace_settings_exists'] is False
    settings_local_path = plan.workspace_path / '.claude' / 'settings.local.json'
    settings_local = json.loads(settings_local_path.read_text(encoding='utf-8'))
    assert settings_local['hooks']['Stop'][0]['hooks'][0]['command']


def test_ensure_agent_runtime_launches_named_codex_session(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    (project_root / '.ccb').mkdir(parents=True)
    ctx = _context(project_root, ParsedStartCommand(project=None, agent_names=('agent1',), restore=False, auto_permission=False))
    spec = _spec('agent1')
    plan = WorkspacePlanner().plan(spec, ctx.project)
    plan.workspace_path.mkdir(parents=True, exist_ok=True)

    tmux_state: dict[str, object] = {}

    class FakeTmuxBackend:
        _socket_name = 'sock-agent'
        _socket_path = '/tmp/ccb-agent.sock'

        def create_pane(self, cmd: str, cwd: str, direction: str = 'right', percent: int = 50, parent_pane: str | None = None) -> str:
            self.cmd = cmd
            self.cwd = cwd
            tmux_state['cwd'] = cwd
            tmux_state['cmd'] = cmd
            return '%42'

        def set_pane_title(self, pane_id: str, title: str) -> None:
            self.title = (pane_id, title)
            tmux_state['title'] = self.title

        def set_pane_user_option(self, pane_id: str, name: str, value: str) -> None:
            self.user_option = (pane_id, name, value)
            tmux_state['user_option'] = self.user_option

        def _tmux_run(self, args, capture=False, timeout=None):
            return subprocess.CompletedProcess(args=args, returncode=0, stdout='4242\n', stderr='')

    spawned: dict[str, object] = {}

    class FakePopen:
        def __init__(self, args, **kwargs):
            env = kwargs.get('env') or {}
            session_file = Path(str(env.get('CCB_SESSION_FILE') or ''))
            assert session_file.is_file()
            spawned.setdefault('calls', []).append((args, kwargs))
            spawned.setdefault('args', args)
            spawned.setdefault('kwargs', kwargs)
            spawned.setdefault('session_file', str(session_file))
            self.pid = 9911

    monkeypatch.setattr('cli.services.runtime_launch._inside_tmux', lambda: True)
    monkeypatch.setattr('cli.services.runtime_launch.shutil.which', lambda name: f'/usr/bin/{name}')
    monkeypatch.setattr('cli.services.runtime_launch.TmuxBackend', FakeTmuxBackend)
    monkeypatch.setattr('cli.services.runtime_launch.subprocess.Popen', FakePopen)

    result = ensure_agent_runtime(ctx, ctx.command, spec, plan, None)

    assert result.launched is True
    assert result.binding is not None
    assert result.binding.runtime_ref == 'tmux:%42'
    expected_session = project_root / '.ccb' / '.codex-agent1-session'
    assert result.binding.session_ref == str(expected_session)
    payload = json.loads(expected_session.read_text(encoding='utf-8'))
    assert payload['pane_id'] == '%42'
    assert payload['agent_name'] == 'agent1'
    assert payload['ccb_project_id'] == ctx.project.project_id
    assert payload['completion_artifact_dir'] == str(ctx.paths.agent_dir('agent1') / 'provider-runtime' / 'codex' / 'completion')
    assert payload['pane_title_marker'].startswith('CCB-agent1-')
    assert payload['tmux_socket_name'] == 'sock-agent'
    assert payload['tmux_socket_path'] == '/tmp/ccb-agent.sock'
    assert payload['work_dir'] == str(plan.workspace_path)
    assert payload['work_dir_norm']
    assert payload['codex_start_cmd'].startswith('export ')
    assert 'disable_paste_burst=true' in payload['codex_start_cmd']
    assert spawned['kwargs']['env']['CCB_SESSION_FILE'] == str(expected_session)
    expected_lib_root = str((Path(codex_launcher.__file__).resolve().parents[2]))
    assert expected_lib_root in str(spawned['kwargs']['env']['PYTHONPATH'])
    assert Path(spawned['kwargs']['stdout'].name) == ctx.paths.agent_dir('agent1') / 'provider-runtime' / 'codex' / 'bridge.stdout.log'
    assert Path(spawned['kwargs']['stderr'].name) == ctx.paths.agent_dir('agent1') / 'provider-runtime' / 'codex' / 'bridge.stderr.log'
    assert tmux_state['title'] == ('%42', 'agent1')
    assert tmux_state['user_option'] == ('%42', '@ccb_project_id', ctx.project.project_id)
    assert (ctx.paths.agent_dir('agent1') / 'provider-runtime' / 'codex' / 'bridge.pid').read_text(encoding='utf-8').strip() == '9911'
    assert (ctx.paths.agent_dir('agent1') / 'provider-runtime' / 'codex' / 'codex.pid').read_text(encoding='utf-8').strip() == '4242'
    assert spawned['args'][0] == __import__('sys').executable
    assert spawned['args'][1:4] == ['-m', 'provider_backends.codex.bridge', '--runtime-dir']


def test_ensure_agent_runtime_uses_agent_scoped_session_name_for_codex_agent(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    (project_root / '.ccb').mkdir(parents=True)
    ctx = _context(project_root, ParsedStartCommand(project=None, agent_names=('codex',), restore=False, auto_permission=False))
    spec = _spec('codex')
    plan = WorkspacePlanner().plan(spec, ctx.project)
    plan.workspace_path.mkdir(parents=True, exist_ok=True)

    class FakeTmuxBackend:
        def create_pane(self, cmd: str, cwd: str, direction: str = 'right', percent: int = 50, parent_pane: str | None = None) -> str:
            return '%7'

        def set_pane_title(self, pane_id: str, title: str) -> None:
            pass

        def set_pane_user_option(self, pane_id: str, name: str, value: str) -> None:
            pass

        def _tmux_run(self, args, capture=False, timeout=None):
            return subprocess.CompletedProcess(args=args, returncode=0, stdout='7000\n', stderr='')

    class FakePopen:
        def __init__(self, args, **kwargs):
            self.pid = 1234

    monkeypatch.setattr('cli.services.runtime_launch._inside_tmux', lambda: True)
    monkeypatch.setattr('cli.services.runtime_launch.shutil.which', lambda name: f'/usr/bin/{name}')
    monkeypatch.setattr('cli.services.runtime_launch.TmuxBackend', FakeTmuxBackend)
    monkeypatch.setattr('cli.services.runtime_launch.subprocess.Popen', FakePopen)

    result = ensure_agent_runtime(ctx, ctx.command, spec, plan, None)

    assert result.binding is not None
    assert result.binding.session_ref == str(project_root / '.ccb' / '.codex-codex-session')


def test_ensure_agent_runtime_passes_profile_codex_home_to_bridge(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-profile-bridge'
    (project_root / '.ccb').mkdir(parents=True)
    ctx = _context(project_root, ParsedStartCommand(project=None, agent_names=('agent1',), restore=False, auto_permission=False))
    spec = _spec('agent1')
    plan = WorkspacePlanner().plan(spec, ctx.project)
    plan.workspace_path.mkdir(parents=True, exist_ok=True)
    runtime_dir = ctx.paths.agent_dir('agent1') / 'provider-runtime' / 'codex'
    profile_home = tmp_path / 'profile-home'
    _write_provider_profile(
        runtime_dir,
        ResolvedProviderProfile(
            provider='codex',
            agent_name='agent1',
            mode='isolated',
            profile_root=str(tmp_path / 'profile-root'),
            runtime_home=str(profile_home),
            env={},
            inherit_api=True,
        ),
    )

    spawned: dict[str, object] = {}

    class FakeTmuxBackend:
        def create_pane(self, cmd: str, cwd: str, direction: str = 'right', percent: int = 50, parent_pane: str | None = None) -> str:
            return '%64'

        def set_pane_title(self, pane_id: str, title: str) -> None:
            pass

        def set_pane_user_option(self, pane_id: str, name: str, value: str) -> None:
            pass

        def _tmux_run(self, args, capture=False, timeout=None):
            return subprocess.CompletedProcess(args=args, returncode=0, stdout='6464\n', stderr='')

    class FakePopen:
        def __init__(self, args, **kwargs):
            env = kwargs.get('env') or {}
            if env.get('CCB_SESSION_FILE'):
                spawned['env'] = env
            self.pid = 8844

    monkeypatch.setattr('cli.services.runtime_launch._inside_tmux', lambda: True)
    monkeypatch.setattr('cli.services.runtime_launch.shutil.which', lambda name: f'/usr/bin/{name}')
    monkeypatch.setattr('cli.services.runtime_launch.TmuxBackend', FakeTmuxBackend)
    monkeypatch.setattr('cli.services.runtime_launch.subprocess.Popen', FakePopen)

    ensure_agent_runtime(ctx, ctx.command, spec, plan, None)

    assert spawned['env']['CODEX_HOME'] == str(profile_home)
    assert spawned['env']['CODEX_SESSION_ROOT'] == str(profile_home / 'sessions')


def test_binding_runtime_alive_uses_tmux_socket_and_active_pane(monkeypatch) -> None:
    calls: list[tuple[str | None, str]] = []

    class FakeTmuxBackend:
        def __init__(self, *, socket_name: str | None = None, socket_path: str | None = None):
            self.socket_name = socket_name
            self.socket_path = socket_path

        def is_tmux_pane_alive(self, pane_id: str) -> bool:
            calls.append((self.socket_name, pane_id))
            return self.socket_name == 'sock-agent' and pane_id == '%77'

    monkeypatch.setattr('cli.services.runtime_launch.TmuxBackend', FakeTmuxBackend)

    binding = AgentBinding(
        runtime_ref='tmux:%41',
        session_ref='session-1',
        tmux_socket_name='sock-agent',
        pane_id='%41',
        active_pane_id='%77',
    )

    assert runtime_launch._binding_runtime_alive(binding) is True
    assert calls == [('sock-agent', '%77')]


def test_binding_runtime_alive_rejects_title_based_runtime_ref(monkeypatch) -> None:
    calls: list[str] = []

    class FakeTmuxBackend:
        def __init__(self, *, socket_name: str | None = None, socket_path: str | None = None):
            self.socket_name = socket_name
            self.socket_path = socket_path

        def is_tmux_pane_alive(self, pane_id: str) -> bool:
            calls.append(pane_id)
            return True

    monkeypatch.setattr('cli.services.runtime_launch.TmuxBackend', FakeTmuxBackend)

    binding = AgentBinding(
        runtime_ref='tmux:title:CCB-agent1-demo',
        session_ref='session-1',
        tmux_socket_name='sock-agent',
        pane_title_marker='CCB-agent1-demo',
    )

    assert runtime_launch._binding_runtime_alive(binding) is False
    assert calls == []


def test_ensure_agent_runtime_resumes_named_codex_session_by_agent_name(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-codex-resume'
    ccb_dir = project_root / '.ccb'
    ccb_dir.mkdir(parents=True)
    (ccb_dir / '.codex-agent1-session').write_text(
        json.dumps({'codex_session_id': 'agent1-session-id'}, ensure_ascii=False),
        encoding='utf-8',
    )
    (ccb_dir / '.codex-agent2-session').write_text(
        json.dumps({'codex_session_id': 'agent2-session-id'}, ensure_ascii=False),
        encoding='utf-8',
    )
    ctx = _context(project_root, ParsedStartCommand(project=None, agent_names=('agent1',), restore=True, auto_permission=False))
    spec = _spec('agent1')
    plan = WorkspacePlanner().plan(spec, ctx.project)
    plan.workspace_path.mkdir(parents=True, exist_ok=True)

    tmux_state: dict[str, object] = {}

    class FakeTmuxBackend:
        def create_pane(self, cmd: str, cwd: str, direction: str = 'right', percent: int = 50, parent_pane: str | None = None) -> str:
            tmux_state['cmd'] = cmd
            tmux_state['cwd'] = cwd
            return '%52'

        def set_pane_title(self, pane_id: str, title: str) -> None:
            tmux_state['title'] = (pane_id, title)

        def set_pane_user_option(self, pane_id: str, name: str, value: str) -> None:
            tmux_state['user_option'] = (pane_id, name, value)

        def _tmux_run(self, args, capture=False, timeout=None):
            return subprocess.CompletedProcess(args=args, returncode=0, stdout='5252\n', stderr='')

    class FakePopen:
        def __init__(self, args, **kwargs):
            self.pid = 9912

    monkeypatch.setattr('cli.services.runtime_launch._inside_tmux', lambda: True)
    monkeypatch.setattr('cli.services.runtime_launch.shutil.which', lambda name: f'/usr/bin/{name}')
    monkeypatch.setattr('cli.services.runtime_launch.TmuxBackend', FakeTmuxBackend)
    monkeypatch.setattr('cli.services.runtime_launch.subprocess.Popen', FakePopen)

    result = ensure_agent_runtime(ctx, ctx.command, spec, plan, None)

    assert result.launched is True
    assert result.binding is not None
    assert result.binding.runtime_ref == 'tmux:%52'
    assert str(tmux_state['cmd']).endswith('resume agent1-session-id')
    assert 'agent2-session-id' not in str(tmux_state['cmd'])
    payload = json.loads((project_root / '.ccb' / '.codex-agent1-session').read_text(encoding='utf-8'))
    assert payload['codex_start_cmd'].endswith('resume agent1-session-id')


def test_ensure_agent_runtime_launches_named_gemini_session(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-gemini'
    (project_root / '.ccb').mkdir(parents=True)
    ctx = _context(project_root, ParsedStartCommand(project=None, agent_names=('reviewer',), restore=True, auto_permission=True))
    spec = _spec('reviewer', provider='gemini')
    plan = WorkspacePlanner().plan(spec, ctx.project)
    plan.workspace_path.mkdir(parents=True, exist_ok=True)

    tmux_state: dict[str, object] = {}

    class FakeTmuxBackend:
        def create_pane(self, cmd: str, cwd: str, direction: str = 'right', percent: int = 50, parent_pane: str | None = None) -> str:
            tmux_state['cmd'] = cmd
            tmux_state['cwd'] = cwd
            return '%55'

        def set_pane_title(self, pane_id: str, title: str) -> None:
            tmux_state['title'] = (pane_id, title)

        def set_pane_user_option(self, pane_id: str, name: str, value: str) -> None:
            tmux_state['user_option'] = (pane_id, name, value)

    resume_dir = tmp_path / 'gemini-resume'
    resume_dir.mkdir()

    monkeypatch.setattr('cli.services.runtime_launch._inside_tmux', lambda: True)
    monkeypatch.setattr('cli.services.runtime_launch.shutil.which', lambda name: f'/usr/bin/{name}')
    monkeypatch.setattr('cli.services.runtime_launch.TmuxBackend', FakeTmuxBackend)
    monkeypatch.setattr(
        gemini_launcher,
        '_resolve_gemini_restore_target',
        lambda **kwargs: ProviderRestoreTarget(run_cwd=resume_dir, has_history=True),
    )

    result = ensure_agent_runtime(ctx, ctx.command, spec, plan, None)

    assert result.launched is True
    assert result.binding is not None
    assert result.binding.runtime_ref == 'tmux:%55'
    expected_session = project_root / '.ccb' / '.gemini-reviewer-session'
    assert result.binding.session_ref == str(expected_session)
    payload = json.loads(expected_session.read_text(encoding='utf-8'))
    assert payload['agent_name'] == 'reviewer'
    assert payload['ccb_project_id'] == ctx.project.project_id
    assert payload['completion_artifact_dir'] == str(ctx.paths.agent_dir('reviewer') / 'provider-runtime' / 'gemini' / 'completion')
    assert payload['pane_title_marker'].startswith('CCB-reviewer-')
    assert payload['pane_id'] == '%55'
    assert payload['work_dir'] == str(resume_dir)
    assert payload['start_cmd'] == 'gemini --yolo --resume latest'
    assert tmux_state['cwd'] == str(resume_dir)
    assert tmux_state['title'] == ('%55', 'reviewer')
    assert tmux_state['user_option'] == ('%55', '@ccb_project_id', ctx.project.project_id)


def test_ensure_agent_runtime_launches_named_claude_session(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-claude'
    (project_root / '.ccb').mkdir(parents=True)
    ctx = _context(project_root, ParsedStartCommand(project=None, agent_names=('reviewer',), restore=True, auto_permission=True))
    spec = _spec('reviewer', provider='claude')
    plan = WorkspacePlanner().plan(spec, ctx.project)
    plan.workspace_path.mkdir(parents=True, exist_ok=True)

    tmux_state: dict[str, object] = {}

    class FakeTmuxBackend:
        def create_pane(self, cmd: str, cwd: str, direction: str = 'right', percent: int = 50, parent_pane: str | None = None) -> str:
            tmux_state['cmd'] = cmd
            tmux_state['cwd'] = cwd
            return '%44'

        def set_pane_title(self, pane_id: str, title: str) -> None:
            tmux_state['title'] = (pane_id, title)

        def set_pane_user_option(self, pane_id: str, name: str, value: str) -> None:
            tmux_state['user_option'] = (pane_id, name, value)

    resume_dir = tmp_path / 'claude-resume'
    resume_dir.mkdir()

    monkeypatch.setattr('cli.services.runtime_launch._inside_tmux', lambda: True)
    monkeypatch.setattr('cli.services.runtime_launch.shutil.which', lambda name: f'/usr/bin/{name}')
    monkeypatch.setattr('cli.services.runtime_launch.TmuxBackend', FakeTmuxBackend)
    monkeypatch.setattr(
        claude_launcher,
        '_resolve_claude_restore_target',
        lambda **kwargs: ProviderRestoreTarget(run_cwd=resume_dir, has_history=True),
    )
    monkeypatch.setattr(
        'provider_backends.claude.launcher.write_claude_settings_overlay',
        lambda runtime_dir, profile=None: runtime_dir / 'claude-settings.json',
    )
    monkeypatch.setattr(
        'provider_backends.claude.launcher.build_claude_env_prefix',
        lambda profile=None, extra_env=None: 'unset ANTHROPIC_BASE_URL',
    )

    result = ensure_agent_runtime(ctx, ctx.command, spec, plan, None)

    assert result.launched is True
    assert result.binding is not None
    assert result.binding.runtime_ref == 'tmux:%44'
    expected_session = project_root / '.ccb' / '.claude-reviewer-session'
    assert result.binding.session_ref == str(expected_session)
    payload = json.loads(expected_session.read_text(encoding='utf-8'))
    assert payload['agent_name'] == 'reviewer'
    assert payload['ccb_project_id'] == ctx.project.project_id
    assert payload['completion_artifact_dir'] == str(ctx.paths.agent_dir('reviewer') / 'provider-runtime' / 'claude' / 'completion')
    assert payload['pane_title_marker'].startswith('CCB-reviewer-')
    assert payload['pane_id'] == '%44'
    assert payload['work_dir'] == str(resume_dir)
    assert payload['ccb_session_id'].startswith('ccb-reviewer-')
    assert tmux_state['cwd'] == str(resume_dir)
    assert payload['start_cmd'] == (
        f'unset ANTHROPIC_BASE_URL; claude --setting-sources user,project,local --settings '
        f'{shlex.quote(str(ctx.paths.agent_dir("reviewer") / "provider-runtime" / "claude" / "claude-settings.json"))} '
        '--dangerously-skip-permissions --continue'
    )
    assert tmux_state['title'] == ('%44', 'reviewer')
    assert tmux_state['user_option'] == ('%44', '@ccb_project_id', ctx.project.project_id)


def test_ensure_agent_runtime_launches_named_opencode_session(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-opencode'
    (project_root / '.ccb').mkdir(parents=True)
    ctx = _context(project_root, ParsedStartCommand(project=None, agent_names=('builder',), restore=True, auto_permission=False))
    spec = _spec('builder', provider='opencode')
    plan = WorkspacePlanner().plan(spec, ctx.project)
    plan.workspace_path.mkdir(parents=True, exist_ok=True)

    class FakeTmuxBackend:
        def create_pane(self, cmd: str, cwd: str, direction: str = 'right', percent: int = 50, parent_pane: str | None = None) -> str:
            self.cmd = cmd
            self.cwd = cwd
            return '%66'

        def set_pane_title(self, pane_id: str, title: str) -> None:
            self.title = (pane_id, title)

        def set_pane_user_option(self, pane_id: str, name: str, value: str) -> None:
            self.user_option = (pane_id, name, value)

    monkeypatch.setattr('cli.services.runtime_launch._inside_tmux', lambda: True)
    monkeypatch.setattr('cli.services.runtime_launch.shutil.which', lambda name: f'/usr/bin/{name}')
    monkeypatch.setattr('cli.services.runtime_launch.TmuxBackend', FakeTmuxBackend)
    monkeypatch.setenv('OPENCODE_START_CMD', 'opencode')

    result = ensure_agent_runtime(ctx, ctx.command, spec, plan, None)

    assert result.launched is True
    assert result.binding is not None
    expected_session = project_root / '.ccb' / '.opencode-builder-session'
    assert result.binding.session_ref == str(expected_session)
    payload = json.loads(expected_session.read_text(encoding='utf-8'))
    assert payload['pane_title_marker'].startswith('CCB-builder-')
    assert payload['start_cmd'] == 'opencode --continue'
    assert payload['ccb_session_id'].startswith('ccb-builder-')


def test_ensure_agent_runtime_uses_assigned_tmux_pane(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-assigned'
    (project_root / '.ccb').mkdir(parents=True)
    ctx = _context(project_root, ParsedStartCommand(project=None, agent_names=('agent1',), restore=False, auto_permission=False))
    spec = _spec('agent1')
    plan = WorkspacePlanner().plan(spec, ctx.project)
    plan.workspace_path.mkdir(parents=True, exist_ok=True)

    tmux_state: dict[str, object] = {'options': [], 'styles': []}

    class FakeTmuxBackend:
        def respawn_pane(self, pane_id: str, *, cmd: str, cwd: str | None = None, remain_on_exit: bool = True) -> None:
            tmux_state['respawn'] = (pane_id, cmd, cwd, remain_on_exit)

        def set_pane_title(self, pane_id: str, title: str) -> None:
            tmux_state['title'] = (pane_id, title)

        def set_pane_user_option(self, pane_id: str, name: str, value: str) -> None:
            tmux_state['options'].append((pane_id, name, value))

        def set_pane_style(
            self,
            pane_id: str,
            *,
            border_style: str | None = None,
            active_border_style: str | None = None,
        ) -> None:
            tmux_state['styles'].append((pane_id, border_style, active_border_style))

        def _tmux_run(self, args, capture=False, timeout=None):
            return subprocess.CompletedProcess(args=args, returncode=0, stdout='4343\n', stderr='')

    spawned: dict[str, object] = {}

    class FakePopen:
        def __init__(self, args, **kwargs):
            spawned['args'] = args
            self.pid = 9913

    monkeypatch.setattr('cli.services.runtime_launch._inside_tmux', lambda: True)
    monkeypatch.setattr('cli.services.runtime_launch.shutil.which', lambda name: f'/usr/bin/{name}')
    monkeypatch.setattr('cli.services.runtime_launch.TmuxBackend', FakeTmuxBackend)
    monkeypatch.setattr('cli.services.runtime_launch.subprocess.Popen', FakePopen)

    result = ensure_agent_runtime(ctx, ctx.command, spec, plan, None, assigned_pane_id='%43', style_index=2)

    assert result.launched is True
    assert result.binding is not None
    assert result.binding.runtime_ref == 'tmux:%43'
    assert tmux_state['respawn'][0] == '%43'
    assert tmux_state['respawn'][2] == str(plan.workspace_path)
    visual = pane_visual(project_id=ctx.project.project_id, slot_key='agent1', order_index=0)
    assert ('%43', '@ccb_label_style', visual.label_style) in tmux_state['options']
    assert ('%43', '@ccb_agent', 'agent1') in tmux_state['options']
    assert ('%43', '@ccb_project_id', ctx.project.project_id) in tmux_state['options']
    assert ('%43', visual.border_style, visual.active_border_style) in tmux_state['styles']


def test_ensure_agent_runtime_launches_named_droid_session(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-droid'
    (project_root / '.ccb').mkdir(parents=True)
    ctx = _context(project_root, ParsedStartCommand(project=None, agent_names=('mobile',), restore=True, auto_permission=False))
    spec = _spec('mobile', provider='droid')
    plan = WorkspacePlanner().plan(spec, ctx.project)
    plan.workspace_path.mkdir(parents=True, exist_ok=True)

    class FakeTmuxBackend:
        def create_pane(self, cmd: str, cwd: str, direction: str = 'right', percent: int = 50, parent_pane: str | None = None) -> str:
            self.cmd = cmd
            self.cwd = cwd
            return '%77'

        def set_pane_title(self, pane_id: str, title: str) -> None:
            self.title = (pane_id, title)

        def set_pane_user_option(self, pane_id: str, name: str, value: str) -> None:
            self.user_option = (pane_id, name, value)

    monkeypatch.setattr('cli.services.runtime_launch._inside_tmux', lambda: True)
    monkeypatch.setattr('cli.services.runtime_launch.shutil.which', lambda name: f'/usr/bin/{name}')
    monkeypatch.setattr('cli.services.runtime_launch.TmuxBackend', FakeTmuxBackend)
    monkeypatch.setenv('DROID_START_CMD', 'droid')

    result = ensure_agent_runtime(ctx, ctx.command, spec, plan, None)

    assert result.launched is True
    assert result.binding is not None
    expected_session = project_root / '.ccb' / '.droid-mobile-session'
    assert result.binding.session_ref == str(expected_session)
    payload = json.loads(expected_session.read_text(encoding='utf-8'))
    assert payload['pane_title_marker'].startswith('CCB-mobile-')
    assert payload['start_cmd'] == 'droid -r'
    assert payload['ccb_session_id'].startswith('ccb-mobile-')


def test_ensure_agent_runtime_falls_back_to_detached_tmux_session(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    (project_root / '.ccb').mkdir(parents=True)
    ctx = _context(project_root, ParsedStartCommand(project=None, agent_names=('agent1',), restore=False, auto_permission=False))
    spec = _spec('agent1')
    plan = WorkspacePlanner().plan(spec, ctx.project)
    plan.workspace_path.mkdir(parents=True, exist_ok=True)

    calls: list[tuple[str, tuple[object, ...]]] = []

    class FakeTmuxBackend:
        def create_pane(self, cmd: str, cwd: str, direction: str = 'right', percent: int = 50, parent_pane: str | None = None) -> str:
            raise RuntimeError('tmux split-window failed (exit 1): no space for new pane')

        def set_pane_title(self, pane_id: str, title: str) -> None:
            calls.append(('title', (pane_id, title)))

        def set_pane_user_option(self, pane_id: str, name: str, value: str) -> None:
            calls.append(('option', (pane_id, name, value)))

        def respawn_pane(self, pane_id: str, *, cmd: str, cwd: str | None = None, remain_on_exit: bool = True) -> None:
            calls.append(('respawn', (pane_id, cmd, cwd, remain_on_exit)))

        def _tmux_run(self, args, capture=False, timeout=None, check=False):
            if args == ['start-server']:
                calls.append(('start-server', tuple(args)))
                return subprocess.CompletedProcess(args=args, returncode=0, stdout='', stderr='')
            if args == ['set-option', '-g', 'destroy-unattached', 'off']:
                calls.append(('set-option', tuple(args)))
                return subprocess.CompletedProcess(args=args, returncode=0, stdout='', stderr='')
            if args[:2] == ['new-session', '-d']:
                calls.append(('new-session', tuple(args)))
                return subprocess.CompletedProcess(args=args, returncode=0, stdout='', stderr='')
            if args[:2] == ['list-panes', '-t']:
                return subprocess.CompletedProcess(args=args, returncode=0, stdout='%88\n', stderr='')
            if args[:2] == ['display-message', '-p']:
                return subprocess.CompletedProcess(args=args, returncode=0, stdout='8800\n', stderr='')
            raise AssertionError(args)

    class FakePopen:
        def __init__(self, args, **kwargs):
            self.pid = 2222

    monkeypatch.setattr('cli.services.runtime_launch._inside_tmux', lambda: True)
    monkeypatch.setattr('cli.services.runtime_launch.shutil.which', lambda name: f'/usr/bin/{name}')
    monkeypatch.setattr('cli.services.runtime_launch.TmuxBackend', FakeTmuxBackend)
    monkeypatch.setattr('cli.services.runtime_launch.subprocess.Popen', FakePopen)
    monkeypatch.setattr('cli.services.runtime_launch._pane_meets_minimum_size', lambda backend, pane_id: True)

    result = ensure_agent_runtime(ctx, ctx.command, spec, plan, None)

    assert result.binding is not None
    assert result.binding.runtime_ref == 'tmux:%88'
    assert any(name == 'start-server' for name, _ in calls)
    assert any(name == 'set-option' for name, _ in calls)
    assert any(name == 'new-session' for name, _ in calls)
    assert any(name == 'respawn' for name, _ in calls)


def test_ensure_agent_runtime_refuses_detached_fallback_inside_project_namespace(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-namespace-no-detached'
    (project_root / '.ccb').mkdir(parents=True)
    ctx = _context(project_root, ParsedStartCommand(project=None, agent_names=('agent1',), restore=False, auto_permission=False))
    spec = _spec('agent1')
    plan = WorkspacePlanner().plan(spec, ctx.project)
    plan.workspace_path.mkdir(parents=True, exist_ok=True)

    class FakeTmuxBackend:
        def __init__(self, *, socket_name: str | None = None, socket_path: str | None = None) -> None:
            self.socket_name = socket_name
            self.socket_path = socket_path

    monkeypatch.setattr('cli.services.runtime_launch._inside_tmux', lambda: True)
    monkeypatch.setattr('cli.services.runtime_launch.shutil.which', lambda name: f'/usr/bin/{name}')
    monkeypatch.setattr('cli.services.runtime_launch.TmuxBackend', FakeTmuxBackend)

    with pytest.raises(RuntimeError, match='project namespace launch requires assigned tmux pane'):
        ensure_agent_runtime(
            ctx,
            ctx.command,
            spec,
            plan,
            None,
            tmux_socket_path=str(project_root / '.ccb' / 'ccbd' / 'tmux.sock'),
        )


def test_ensure_agent_runtime_relaunches_when_existing_binding_pane_is_dead(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-dead-binding'
    (project_root / '.ccb').mkdir(parents=True)
    ctx = _context(project_root, ParsedStartCommand(project=None, agent_names=('reviewer',), restore=False, auto_permission=False))
    spec = _spec('reviewer', provider='gemini')
    plan = WorkspacePlanner().plan(spec, ctx.project)
    plan.workspace_path.mkdir(parents=True, exist_ok=True)
    tmux_state: dict[str, object] = {'killed': []}

    class FakeTmuxBackend:
        def __init__(self, *, socket_name: str | None = None, socket_path: str | None = None) -> None:
            self.socket_name = socket_name
            self.socket_path = socket_path

        def is_tmux_pane_alive(self, pane_id: str) -> bool:
            return False

        def kill_tmux_pane(self, pane_id: str) -> None:
            tmux_state['killed'].append((self.socket_name, pane_id))

        def create_pane(self, cmd: str, cwd: str, direction: str = 'right', percent: int = 50, parent_pane: str | None = None) -> str:
            self.cmd = cmd
            self.cwd = cwd
            return '%91'

        def set_pane_title(self, pane_id: str, title: str) -> None:
            self.title = (pane_id, title)

        def set_pane_user_option(self, pane_id: str, name: str, value: str) -> None:
            self.user_option = (pane_id, name, value)

    monkeypatch.setattr('cli.services.runtime_launch._inside_tmux', lambda: True)
    monkeypatch.setattr('cli.services.runtime_launch.shutil.which', lambda name: f'/usr/bin/{name}')
    monkeypatch.setattr('cli.services.runtime_launch.TmuxBackend', FakeTmuxBackend)

    result = ensure_agent_runtime(
        ctx,
        ctx.command,
        spec,
        plan,
        AgentBinding(
            runtime_ref='tmux:%44',
            session_ref=str(project_root / '.ccb' / '.gemini-reviewer-session'),
            tmux_socket_name='sock-dead',
            pane_id='%44',
            pane_state='dead',
        ),
    )

    assert result.launched is True
    assert result.binding is not None
    assert result.binding.runtime_ref == 'tmux:%91'
    assert tmux_state['killed'] == [('sock-dead', '%44')]


def test_ensure_agent_runtime_outside_tmux_relaunches_stale_binding_via_detached_session(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-outside-tmux-stale'
    (project_root / '.ccb').mkdir(parents=True)
    ctx = _context(project_root, ParsedStartCommand(project=None, agent_names=('agent1',), restore=False, auto_permission=False))
    spec = _spec('agent1')
    plan = WorkspacePlanner().plan(spec, ctx.project)
    plan.workspace_path.mkdir(parents=True, exist_ok=True)

    calls: list[tuple[str, tuple[object, ...]]] = []

    class FakeTmuxBackend:
        def __init__(self, *, socket_name: str | None = None, socket_path: str | None = None) -> None:
            self.socket_name = socket_name
            self.socket_path = socket_path

        def is_tmux_pane_alive(self, pane_id: str) -> bool:
            return False

        def kill_tmux_pane(self, pane_id: str) -> None:
            calls.append(('kill', (self.socket_name, pane_id)))

        def create_pane(self, cmd: str, cwd: str, direction: str = 'right', percent: int = 50, parent_pane: str | None = None) -> str:
            raise RuntimeError('tmux split-window failed (exit 1): no space for new pane')

        def set_pane_title(self, pane_id: str, title: str) -> None:
            calls.append(('title', (pane_id, title)))

        def set_pane_user_option(self, pane_id: str, name: str, value: str) -> None:
            calls.append(('option', (pane_id, name, value)))

        def respawn_pane(self, pane_id: str, *, cmd: str, cwd: str | None = None, remain_on_exit: bool = True) -> None:
            calls.append(('respawn', (pane_id, cmd, cwd, remain_on_exit)))

        def _tmux_run(self, args, capture=False, timeout=None, check=False):
            if args == ['start-server']:
                calls.append(('start-server', tuple(args)))
                return subprocess.CompletedProcess(args=args, returncode=0, stdout='', stderr='')
            if args == ['set-option', '-g', 'destroy-unattached', 'off']:
                calls.append(('set-option', tuple(args)))
                return subprocess.CompletedProcess(args=args, returncode=0, stdout='', stderr='')
            if args[:2] == ['new-session', '-d']:
                calls.append(('new-session', tuple(args)))
                return subprocess.CompletedProcess(args=args, returncode=0, stdout='', stderr='')
            if args[:2] == ['list-panes', '-t']:
                return subprocess.CompletedProcess(args=args, returncode=0, stdout='%88\n', stderr='')
            if args[:2] == ['display-message', '-p']:
                return subprocess.CompletedProcess(args=args, returncode=0, stdout='8800\n', stderr='')
            raise AssertionError(args)

    class FakePopen:
        def __init__(self, args, **kwargs):
            self.pid = 2222

    monkeypatch.setattr('cli.services.runtime_launch._inside_tmux', lambda: False)
    monkeypatch.setattr('cli.services.runtime_launch.shutil.which', lambda name: f'/usr/bin/{name}')
    monkeypatch.setattr('cli.services.runtime_launch.TmuxBackend', FakeTmuxBackend)
    monkeypatch.setattr('cli.services.runtime_launch.subprocess.Popen', FakePopen)
    monkeypatch.setattr('cli.services.runtime_launch._pane_meets_minimum_size', lambda backend, pane_id: True)

    result = ensure_agent_runtime(
        ctx,
        ctx.command,
        spec,
        plan,
        AgentBinding(
            runtime_ref='tmux:%44',
            session_ref=str(project_root / '.ccb' / '.codex-agent1-session'),
            tmux_socket_name='sock-dead',
            pane_id='%44',
            pane_state='dead',
        ),
    )

    assert result.launched is True
    assert result.binding is not None
    assert result.binding.runtime_ref == 'tmux:%88'
    assert ('kill', ('sock-dead', '%44')) in calls
    assert any(name == 'start-server' for name, _ in calls)
    assert any(name == 'new-session' for name, _ in calls)
    assert any(name == 'respawn' for name, _ in calls)


def test_ensure_agent_runtime_relaunches_live_foreign_binding_without_killing_foreign_pane(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-foreign-binding'
    (project_root / '.ccb').mkdir(parents=True)
    ctx = _context(project_root, ParsedStartCommand(project=None, agent_names=('agent1',), restore=False, auto_permission=False))
    spec = _spec('agent1')
    plan = WorkspacePlanner().plan(spec, ctx.project)
    plan.workspace_path.mkdir(parents=True, exist_ok=True)

    calls: list[tuple[str, tuple[object, ...]]] = []

    class FakeTmuxBackend:
        def __init__(self, *, socket_name: str | None = None, socket_path: str | None = None) -> None:
            self.socket_name = socket_name
            self.socket_path = socket_path

        def is_tmux_pane_alive(self, pane_id: str) -> bool:
            return True

        def kill_tmux_pane(self, pane_id: str) -> None:
            calls.append(('kill', (self.socket_name, pane_id)))

        def create_pane(self, cmd: str, cwd: str, direction: str = 'right', percent: int = 50, parent_pane: str | None = None) -> str:
            calls.append(('create', (cmd, cwd, direction, percent, parent_pane)))
            return '%91'

        def set_pane_title(self, pane_id: str, title: str) -> None:
            calls.append(('title', (pane_id, title)))

        def set_pane_user_option(self, pane_id: str, name: str, value: str) -> None:
            calls.append(('option', (pane_id, name, value)))

    class FakePopen:
        def __init__(self, args, **kwargs):
            self.pid = 1234

    monkeypatch.setattr('cli.services.runtime_launch._inside_tmux', lambda: True)
    monkeypatch.setattr('cli.services.runtime_launch.shutil.which', lambda name: f'/usr/bin/{name}')
    monkeypatch.setattr('cli.services.runtime_launch.TmuxBackend', FakeTmuxBackend)
    monkeypatch.setattr('cli.services.runtime_launch.subprocess.Popen', FakePopen)

    result = ensure_agent_runtime(
        ctx,
        ctx.command,
        spec,
        plan,
        AgentBinding(
            runtime_ref='tmux:%44',
            session_ref=str(project_root / '.ccb' / '.codex-agent1-session'),
            tmux_socket_name='sock-foreign',
            pane_id='%44',
            pane_state='foreign',
        ),
    )

    assert result.launched is True
    assert result.binding is not None
    assert result.binding.runtime_ref == 'tmux:%91'
    assert not any(name == 'kill' for name, _ in calls)
    assert any(name == 'create' for name, _ in calls)


def test_ensure_agent_runtime_raises_when_launch_does_not_produce_usable_binding(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-missing-binding'
    (project_root / '.ccb').mkdir(parents=True)
    ctx = _context(project_root, ParsedStartCommand(project=None, agent_names=('agent1',), restore=False, auto_permission=False))
    spec = _spec('agent1')
    plan = WorkspacePlanner().plan(spec, ctx.project)
    plan.workspace_path.mkdir(parents=True, exist_ok=True)

    class FakeTmuxBackend:
        def create_pane(self, cmd: str, cwd: str, direction: str = 'right', percent: int = 50, parent_pane: str | None = None) -> str:
            return '%42'

        def set_pane_title(self, pane_id: str, title: str) -> None:
            pass

        def set_pane_user_option(self, pane_id: str, name: str, value: str) -> None:
            pass

    class FakePopen:
        def __init__(self, args, **kwargs):
            self.pid = 9911

    monkeypatch.setattr('cli.services.runtime_launch._inside_tmux', lambda: True)
    monkeypatch.setattr('cli.services.runtime_launch.shutil.which', lambda name: f'/usr/bin/{name}')
    monkeypatch.setattr('cli.services.runtime_launch.TmuxBackend', FakeTmuxBackend)
    monkeypatch.setattr('cli.services.runtime_launch.subprocess.Popen', FakePopen)
    monkeypatch.setattr('cli.services.runtime_launch.resolve_agent_binding', lambda **kwargs: None)

    with pytest.raises(RuntimeError, match='failed to resolve usable binding'):
        ensure_agent_runtime(ctx, ctx.command, spec, plan, None)


def test_inside_tmux_detects_tmux_session_without_extra_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('TMUX', '/tmp/tmux-1000/default,1,0')
    monkeypatch.delenv('TMUX_PANE', raising=False)

    assert runtime_launch._inside_tmux() is True


def test_inside_tmux_detects_tmux_pane_without_extra_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv('TMUX', raising=False)
    monkeypatch.setenv('TMUX_PANE', '%7')

    assert runtime_launch._inside_tmux() is True


def test_provider_start_parts_respect_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('GEMINI_START_CMD', '/tmp/stub-gemini --flag')
    monkeypatch.setenv('CLAUDE_START_CMD', '/tmp/stub-claude')
    monkeypatch.setenv('CODEX_START_CMD', '/tmp/stub-codex --profile test')

    assert runtime_launch._provider_start_parts('gemini') == ['/tmp/stub-gemini', '--flag']
    assert runtime_launch._provider_start_parts('claude') == ['/tmp/stub-claude']
    assert runtime_launch._provider_start_parts('codex') == ['/tmp/stub-codex', '--profile', 'test']
    assert runtime_launch._provider_executable('codex') == '/tmp/stub-codex'


def test_provider_start_parts_fall_back_to_default_binary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv('GEMINI_START_CMD', raising=False)
    monkeypatch.delenv('CLAUDE_START_CMD', raising=False)
    monkeypatch.delenv('CODEX_START_CMD', raising=False)

    assert runtime_launch._provider_start_parts('gemini') == ['gemini']
    assert runtime_launch._provider_start_parts('claude') == ['claude']
    assert runtime_launch._provider_start_parts('codex') == ['codex']


def test_ensure_agent_runtime_falls_back_when_created_pane_is_too_small(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    (project_root / '.ccb').mkdir(parents=True)
    ctx = _context(project_root, ParsedStartCommand(project=None, agent_names=('agent1',), restore=False, auto_permission=False))
    spec = _spec('agent1')
    plan = WorkspacePlanner().plan(spec, ctx.project)
    plan.workspace_path.mkdir(parents=True, exist_ok=True)

    calls: list[tuple[str, tuple[object, ...]]] = []

    class FakeTmuxBackend:
        def create_pane(self, cmd: str, cwd: str, direction: str = 'right', percent: int = 50, parent_pane: str | None = None) -> str:
            calls.append(('create', (cmd, cwd)))
            return '%42'

        def kill_tmux_pane(self, pane_id: str) -> None:
            calls.append(('kill', (pane_id,)))

        def set_pane_title(self, pane_id: str, title: str) -> None:
            calls.append(('title', (pane_id, title)))

        def set_pane_user_option(self, pane_id: str, name: str, value: str) -> None:
            calls.append(('option', (pane_id, name, value)))

        def respawn_pane(self, pane_id: str, *, cmd: str, cwd: str | None = None, remain_on_exit: bool = True) -> None:
            calls.append(('respawn', (pane_id, cmd, cwd, remain_on_exit)))

        def _tmux_run(self, args, capture=False, timeout=None, check=False):
            if args == ['start-server']:
                calls.append(('start-server', tuple(args)))
                return subprocess.CompletedProcess(args=args, returncode=0, stdout='', stderr='')
            if args == ['set-option', '-g', 'destroy-unattached', 'off']:
                calls.append(('set-option', tuple(args)))
                return subprocess.CompletedProcess(args=args, returncode=0, stdout='', stderr='')
            if args[:4] == ['new-session', '-d', '-x', '160']:
                calls.append(('new-session', tuple(args)))
                return subprocess.CompletedProcess(args=args, returncode=0, stdout='', stderr='')
            if args[:2] == ['list-panes', '-t']:
                return subprocess.CompletedProcess(args=args, returncode=0, stdout='%88\n', stderr='')
            if args[:2] == ['display-message', '-p']:
                return subprocess.CompletedProcess(args=args, returncode=0, stdout='8800\n', stderr='')
            raise AssertionError(args)

    class FakePopen:
        def __init__(self, args, **kwargs):
            self.pid = 2222

    monkeypatch.setattr('cli.services.runtime_launch._inside_tmux', lambda: True)
    monkeypatch.setattr('cli.services.runtime_launch.shutil.which', lambda name: f'/usr/bin/{name}')
    monkeypatch.setattr('cli.services.runtime_launch.TmuxBackend', FakeTmuxBackend)
    monkeypatch.setattr('cli.services.runtime_launch.subprocess.Popen', FakePopen)
    monkeypatch.setattr('cli.services.runtime_launch._pane_meets_minimum_size', lambda backend, pane_id: False)

    result = ensure_agent_runtime(ctx, ctx.command, spec, plan, None)

    assert result.binding is not None
    assert result.binding.runtime_ref == 'tmux:%88'
    assert ('kill', ('%42',)) in calls
    assert any(name == 'start-server' for name, _ in calls)
    assert any(name == 'set-option' for name, _ in calls)
    assert any(name == 'new-session' for name, _ in calls)
    assert any(name == 'respawn' for name, _ in calls)


def test_codex_launcher_build_start_cmd_isolates_invalid_global_codex_config(monkeypatch, tmp_path: Path) -> None:
    runtime_dir = tmp_path / 'runtime'
    runtime_dir.mkdir(parents=True, exist_ok=True)
    source_home = tmp_path / 'source-home'
    source_home.mkdir(parents=True, exist_ok=True)
    (source_home / 'config.toml').write_text('[mcp_servers.puppeteer]\nfoo=1\n[mcp_servers.puppeteer]\nbar=2\n', encoding='utf-8')
    (source_home / 'auth.json').write_text('{"OPENAI_API_KEY":"test-key"}', encoding='utf-8')
    monkeypatch.setenv('CODEX_HOME', str(source_home))

    spec = _spec('agent1')
    command = ParsedStartCommand(project=None, agent_names=('agent1',), restore=False, auto_permission=False)

    cmd = codex_launcher.build_start_cmd(command, spec, runtime_dir, 'sess-1')

    isolated_home = runtime_dir / 'codex-home'
    assert f'CODEX_HOME={shlex.quote(str(isolated_home))}' in cmd
    assert f'CODEX_SESSION_ROOT={shlex.quote(str(isolated_home / "sessions"))}' in cmd
    assert (isolated_home / 'auth.json').is_file()
    assert (isolated_home / 'config.toml').is_file()


def test_codex_launcher_build_start_cmd_uses_agent_scoped_resume_session(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-codex-resume'
    runtime_dir = project_root / '.ccb' / 'agents' / 'agent1' / 'provider-runtime' / 'codex'
    runtime_dir.mkdir(parents=True, exist_ok=True)
    ccb_dir = project_root / '.ccb'
    ccb_dir.mkdir(parents=True, exist_ok=True)
    (ccb_dir / '.codex-agent1-session').write_text(
        json.dumps(
            {
                'codex_session_id': 'agent1-session-id',
                'codex_start_cmd': 'codex resume agent1-session-id',
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding='utf-8',
    )
    (ccb_dir / '.codex-agent2-session').write_text(
        json.dumps(
            {
                'codex_session_id': 'agent2-session-id',
                'codex_start_cmd': 'codex resume agent2-session-id',
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding='utf-8',
    )

    spec = _spec('agent1')
    command = ParsedStartCommand(project=None, agent_names=('agent1',), restore=True, auto_permission=False)

    monkeypatch.delenv('CODEX_HOME', raising=False)

    cmd = codex_launcher.build_start_cmd(command, spec, runtime_dir, 'sess-restore')

    assert cmd.endswith('resume agent1-session-id')
    assert 'agent2-session-id' not in cmd


def test_codex_launcher_build_start_cmd_reads_resume_cmd_from_agent_scoped_session_file(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-codex-agent'
    runtime_dir = project_root / '.ccb' / 'agents' / 'codex' / 'provider-runtime' / 'codex'
    runtime_dir.mkdir(parents=True, exist_ok=True)
    ccb_dir = project_root / '.ccb'
    ccb_dir.mkdir(parents=True, exist_ok=True)
    (ccb_dir / '.codex-codex-session').write_text(
        json.dumps(
            {
                'codex_start_cmd': 'export CODEX_HOME=/tmp/demo; codex -c disable_paste_burst=true resume codex-session-id',
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding='utf-8',
    )

    spec = _spec('codex')
    command = ParsedStartCommand(project=None, agent_names=('codex',), restore=True, auto_permission=False)

    cmd = codex_launcher.build_start_cmd(command, spec, runtime_dir, 'sess-restore')

    assert cmd.endswith('resume codex-session-id')


def test_claude_launcher_build_start_cmd_uses_overlay_and_drops_dead_local_user_proxy(monkeypatch, tmp_path: Path) -> None:
    runtime_dir = tmp_path / 'runtime'
    runtime_dir.mkdir(parents=True, exist_ok=True)
    home_dir = tmp_path / 'home'
    claude_dir = home_dir / '.claude'
    claude_dir.mkdir(parents=True, exist_ok=True)
    (claude_dir / 'settings.json').write_text(
        json.dumps(
            {
                'env': {
                    'ANTHROPIC_BASE_URL': 'http://127.0.0.1:15722',
                    'ANTHROPIC_AUTH_TOKEN': 'secret',
                },
                'model': 'opus',
                'skipDangerousModePermissionPrompt': True,
            },
            ensure_ascii=False,
        ),
        encoding='utf-8',
    )
    spec = _spec('reviewer', provider='claude')
    command = ParsedStartCommand(project=None, agent_names=('reviewer',), restore=True, auto_permission=True)

    monkeypatch.setattr('provider_backends.claude.launcher.Path.home', lambda: home_dir)
    monkeypatch.setattr('provider_backends.claude.launcher.local_tcp_listener_available', lambda host, port: False)
    monkeypatch.setattr(
        claude_launcher,
        '_resolve_claude_restore_target',
        lambda **kwargs: ProviderRestoreTarget(run_cwd=runtime_dir, has_history=True),
    )

    start_cmd = claude_launcher.build_start_cmd(command, spec, runtime_dir, 'claude-sess-1')

    assert start_cmd == (
        'unset ANTHROPIC_BASE_URL; '
        'claude --setting-sources user,project,local --dangerously-skip-permissions --continue'
    )
    assert not (runtime_dir / 'claude-settings.json').exists()



def test_codex_launcher_build_start_cmd_uses_materialized_profile_home(monkeypatch, tmp_path: Path) -> None:
    runtime_dir = tmp_path / 'runtime'
    profile_home = tmp_path / 'codex-profile-home'
    _write_provider_profile(
        runtime_dir,
        ResolvedProviderProfile(
            provider='codex',
            agent_name='agent1',
            mode='isolated',
            profile_root=str(profile_home),
            runtime_home=str(profile_home),
            env={'OPENAI_API_KEY': 'profile-key'},
            inherit_api=False,
        ),
    )

    spec = _spec('agent1')
    command = ParsedStartCommand(project=None, agent_names=('agent1',), restore=False, auto_permission=False)

    cmd = codex_launcher.build_start_cmd(command, spec, runtime_dir, 'sess-profile')

    assert 'unset OPENAI_API_KEY' in cmd
    assert f'CODEX_HOME={shlex.quote(str(profile_home))}' in cmd
    assert f'CODEX_SESSION_ROOT={shlex.quote(str(profile_home / "sessions"))}' in cmd
    assert f'OPENAI_API_KEY={shlex.quote("profile-key")}' in cmd
    assert (profile_home / 'sessions').is_dir()


def test_claude_launcher_build_start_cmd_uses_isolated_profile_api_env(monkeypatch, tmp_path: Path) -> None:
    runtime_dir = tmp_path / 'runtime'
    runtime_dir.mkdir(parents=True, exist_ok=True)
    home_dir = tmp_path / 'home'
    claude_dir = home_dir / '.claude'
    claude_dir.mkdir(parents=True, exist_ok=True)
    (claude_dir / 'settings.json').write_text(
        json.dumps(
            {
                'env': {
                    'ANTHROPIC_BASE_URL': 'https://example.invalid/claude',
                    'ANTHROPIC_AUTH_TOKEN': 'secret',
                },
                'model': 'opus',
            },
            ensure_ascii=False,
        ),
        encoding='utf-8',
    )
    _write_provider_profile(
        runtime_dir,
        ResolvedProviderProfile(
            provider='claude',
            agent_name='reviewer',
            mode='isolated',
            profile_root=str(tmp_path / 'profile'),
            runtime_home=None,
            env={'ANTHROPIC_AUTH_TOKEN': 'profile-token'},
            inherit_api=False,
        ),
    )
    spec = _spec('reviewer', provider='claude')
    command = ParsedStartCommand(project=None, agent_names=('reviewer',), restore=True, auto_permission=True)

    monkeypatch.setattr('provider_backends.claude.launcher.Path.home', lambda: home_dir)
    monkeypatch.setattr(
        claude_launcher,
        '_resolve_claude_restore_target',
        lambda **kwargs: ProviderRestoreTarget(run_cwd=runtime_dir, has_history=True),
    )

    start_cmd = claude_launcher.build_start_cmd(command, spec, runtime_dir, 'claude-sess-iso')

    assert 'unset ANTHROPIC_AUTH_TOKEN' in start_cmd
    assert f'ANTHROPIC_AUTH_TOKEN={shlex.quote("profile-token")}' in start_cmd
    assert 'https://example.invalid/claude' not in start_cmd
    assert '--settings' not in start_cmd
    assert not (runtime_dir / 'claude-settings.json').exists()


def test_claude_launcher_build_start_cmd_uses_agent_settings_overlay_when_present(monkeypatch, tmp_path: Path) -> None:
    runtime_dir = tmp_path / 'runtime'
    profile_root = tmp_path / 'profile'
    runtime_dir.mkdir(parents=True, exist_ok=True)
    profile_root.mkdir(parents=True, exist_ok=True)
    (profile_root / 'settings.json').write_text(
        json.dumps(
            {
                'env': {'ANTHROPIC_AUTH_TOKEN': 'secret'},
                'model': 'opus',
            },
            ensure_ascii=False,
        ),
        encoding='utf-8',
    )
    _write_provider_profile(
        runtime_dir,
        ResolvedProviderProfile(
            provider='claude',
            agent_name='reviewer',
            mode='inherit',
            profile_root=str(profile_root),
            runtime_home=None,
            env={},
            inherit_api=True,
        ),
    )
    spec = _spec('reviewer', provider='claude')
    command = ParsedStartCommand(project=None, agent_names=('reviewer',), restore=True, auto_permission=False)

    monkeypatch.setattr('provider_backends.claude.launcher.Path.home', lambda: tmp_path / 'home')
    monkeypatch.setattr(
        claude_launcher,
        '_resolve_claude_restore_target',
        lambda **kwargs: ProviderRestoreTarget(run_cwd=runtime_dir, has_history=False),
    )

    start_cmd = claude_launcher.build_start_cmd(command, spec, runtime_dir, 'claude-sess-local')

    settings_path = runtime_dir / 'claude-settings.json'
    assert start_cmd == (
        f'claude --setting-sources user,project,local --settings {shlex.quote(str(settings_path))}'
    )
    assert json.loads(settings_path.read_text(encoding='utf-8')) == {'model': 'opus'}


def test_gemini_launcher_build_start_cmd_uses_isolated_profile_api_env(tmp_path: Path) -> None:
    runtime_dir = tmp_path / 'runtime'
    _write_provider_profile(
        runtime_dir,
        ResolvedProviderProfile(
            provider='gemini',
            agent_name='reviewer',
            mode='isolated',
            profile_root=str(tmp_path / 'profile'),
            runtime_home=None,
            env={'GEMINI_API_KEY': 'gemini-key'},
            inherit_api=False,
        ),
    )
    spec = _spec('reviewer', provider='gemini')
    command = ParsedStartCommand(project=None, agent_names=('reviewer',), restore=False, auto_permission=False)

    start_cmd = gemini_launcher.build_start_cmd(command, spec, runtime_dir, 'gemini-sess-iso')

    assert 'unset GEMINI_API_KEY' in start_cmd
    assert f'GEMINI_API_KEY={shlex.quote("gemini-key")}' in start_cmd
    assert start_cmd.endswith('gemini')
