from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path

from agents.models import AgentSpec, PermissionMode, QueuePolicy, RestoreMode, RuntimeMode, WorkspaceMode
from cli.models import ParsedStartCommand
from provider_backends.claude import launcher as claude_launcher
from provider_backends.gemini import launcher as gemini_launcher


def _spec(name: str, provider: str) -> AgentSpec:
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


def test_claude_restore_prefers_project_session_work_dir(monkeypatch, tmp_path: Path) -> None:
    home_dir = tmp_path / 'home'
    project_root = tmp_path / 'repo'
    runtime_dir = project_root / '.ccb' / 'agents' / 'reviewer' / 'provider-runtime' / 'claude'
    workspace_path = project_root / '.ccb' / 'workspaces' / 'reviewer'
    runtime_dir.mkdir(parents=True)
    workspace_path.mkdir(parents=True)

    session_path = project_root / '.ccb' / '.claude-reviewer-session'
    session_path.parent.mkdir(parents=True, exist_ok=True)
    session_path.write_text(
        json.dumps({'work_dir': str(workspace_path), 'claude_session_id': 'claude-sess-1'}, ensure_ascii=False),
        encoding='utf-8',
    )

    project_dir = home_dir / '.claude' / 'projects' / ''.join(ch if ch.isalnum() else '-' for ch in str(workspace_path))
    session_env_root = home_dir / '.claude' / 'session-env'
    project_dir.mkdir(parents=True)
    session_env_root.mkdir(parents=True)
    session_id = str(uuid.uuid4())
    (project_dir / f'{session_id}.jsonl').write_text('history\n', encoding='utf-8')
    (session_env_root / session_id).mkdir()

    monkeypatch.setattr(claude_launcher.Path, 'home', lambda: home_dir)

    target = claude_launcher._resolve_claude_restore_target(
        spec=_spec('reviewer', 'claude'),
        runtime_dir=runtime_dir,
        workspace_path=workspace_path,
        restore=True,
    )

    assert target.has_history is True
    assert target.run_cwd == workspace_path


def test_gemini_restore_prefers_project_session_work_dir(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    runtime_dir = project_root / '.ccb' / 'agents' / 'reviewer' / 'provider-runtime' / 'gemini'
    workspace_path = project_root / '.ccb' / 'workspaces' / 'reviewer'
    runtime_dir.mkdir(parents=True)
    workspace_path.mkdir(parents=True)

    session_path = project_root / '.ccb' / '.gemini-reviewer-session'
    session_path.parent.mkdir(parents=True, exist_ok=True)
    session_path.write_text(
        json.dumps({'work_dir': str(workspace_path), 'gemini_session_id': 'gemini-sess-1'}, ensure_ascii=False),
        encoding='utf-8',
    )

    gemini_root = tmp_path / 'gemini-root'
    project_hash = hashlib.sha256(str(workspace_path).encode()).hexdigest()
    chats_dir = gemini_root / project_hash / 'chats'
    chats_dir.mkdir(parents=True)
    (chats_dir / 'session-1.json').write_text('{}', encoding='utf-8')
    monkeypatch.setenv('GEMINI_ROOT', str(gemini_root))

    target = gemini_launcher._resolve_gemini_restore_target(
        spec=_spec('reviewer', 'gemini'),
        runtime_dir=runtime_dir,
        workspace_path=workspace_path,
        restore=True,
    )

    assert target.has_history is True
    assert target.run_cwd == workspace_path


def test_claude_build_start_cmd_skips_continue_without_history(monkeypatch, tmp_path: Path) -> None:
    home_dir = tmp_path / 'home'
    runtime_dir = tmp_path / 'repo' / '.ccb' / 'agents' / 'reviewer' / 'provider-runtime' / 'claude'
    runtime_dir.mkdir(parents=True)
    monkeypatch.setattr(claude_launcher.Path, 'home', lambda: home_dir)

    cmd = claude_launcher.build_start_cmd(
        ParsedStartCommand(project=None, agent_names=('reviewer',), restore=True, auto_permission=False),
        _spec('reviewer', 'claude'),
        runtime_dir,
        'launch-1',
    )

    assert '--continue' not in cmd


def test_gemini_build_start_cmd_skips_resume_without_history(tmp_path: Path) -> None:
    runtime_dir = tmp_path / 'repo' / '.ccb' / 'agents' / 'reviewer' / 'provider-runtime' / 'gemini'
    runtime_dir.mkdir(parents=True)

    cmd = gemini_launcher.build_start_cmd(
        ParsedStartCommand(project=None, agent_names=('reviewer',), restore=True, auto_permission=False),
        _spec('reviewer', 'gemini'),
        runtime_dir,
        'launch-1',
    )

    assert '--resume latest' not in cmd


def test_claude_build_start_cmd_skips_continue_when_restore_disabled_even_with_history(monkeypatch, tmp_path: Path) -> None:
    home_dir = tmp_path / 'home'
    project_root = tmp_path / 'repo'
    runtime_dir = project_root / '.ccb' / 'agents' / 'reviewer' / 'provider-runtime' / 'claude'
    workspace_path = project_root / '.ccb' / 'workspaces' / 'reviewer'
    runtime_dir.mkdir(parents=True)
    workspace_path.mkdir(parents=True)

    session_path = project_root / '.ccb' / '.claude-reviewer-session'
    session_path.parent.mkdir(parents=True, exist_ok=True)
    session_path.write_text(
        json.dumps({'work_dir': str(workspace_path), 'claude_session_id': 'claude-sess-1'}, ensure_ascii=False),
        encoding='utf-8',
    )

    project_dir = home_dir / '.claude' / 'projects' / ''.join(ch if ch.isalnum() else '-' for ch in str(workspace_path))
    session_env_root = home_dir / '.claude' / 'session-env'
    project_dir.mkdir(parents=True)
    session_env_root.mkdir(parents=True)
    session_id = str(uuid.uuid4())
    (project_dir / f'{session_id}.jsonl').write_text('history\n', encoding='utf-8')
    (session_env_root / session_id).mkdir()
    monkeypatch.setattr(claude_launcher.Path, 'home', lambda: home_dir)

    cmd = claude_launcher.build_start_cmd(
        ParsedStartCommand(project=None, agent_names=('reviewer',), restore=False, auto_permission=True, reset_context=True),
        _spec('reviewer', 'claude'),
        runtime_dir,
        'launch-1',
    )

    assert '--continue' not in cmd


def test_gemini_build_start_cmd_skips_resume_when_restore_disabled_even_with_history(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    runtime_dir = project_root / '.ccb' / 'agents' / 'reviewer' / 'provider-runtime' / 'gemini'
    workspace_path = project_root / '.ccb' / 'workspaces' / 'reviewer'
    runtime_dir.mkdir(parents=True)
    workspace_path.mkdir(parents=True)

    session_path = project_root / '.ccb' / '.gemini-reviewer-session'
    session_path.parent.mkdir(parents=True, exist_ok=True)
    session_path.write_text(
        json.dumps({'work_dir': str(workspace_path), 'gemini_session_id': 'gemini-sess-1'}, ensure_ascii=False),
        encoding='utf-8',
    )

    gemini_root = tmp_path / 'gemini-root'
    project_hash = hashlib.sha256(str(workspace_path).encode()).hexdigest()
    chats_dir = gemini_root / project_hash / 'chats'
    chats_dir.mkdir(parents=True)
    (chats_dir / 'session-1.json').write_text('{}', encoding='utf-8')
    monkeypatch.setenv('GEMINI_ROOT', str(gemini_root))

    cmd = gemini_launcher.build_start_cmd(
        ParsedStartCommand(project=None, agent_names=('reviewer',), restore=False, auto_permission=True, reset_context=True),
        _spec('reviewer', 'gemini'),
        runtime_dir,
        'launch-1',
    )

    assert '--resume latest' not in cmd
