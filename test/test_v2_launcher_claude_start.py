from __future__ import annotations

from pathlib import Path

import pytest

from launcher.claude_start import LauncherClaudeStartPlanner


def test_claude_start_planner_builds_resume_plan_with_history(tmp_path: Path) -> None:
    resume_dir = tmp_path / 'history'
    planner = LauncherClaudeStartPlanner(
        auto=True,
        resume=True,
        project_root=tmp_path / 'project',
        invocation_dir=tmp_path / 'invoke',
        platform_name='linux',
        env={},
        which_fn=lambda cmd: '/usr/bin/claude' if cmd == 'claude' else None,
        get_latest_session_fn=lambda: ('sess-1', True, resume_dir),
    )

    plan = planner.build_plan()

    assert plan.cmd == ['/usr/bin/claude', '--dangerously-skip-permissions', '--continue']
    assert plan.run_cwd == str(resume_dir)
    assert plan.has_history is True


def test_claude_start_planner_builds_fresh_resume_plan_without_history(tmp_path: Path) -> None:
    planner = LauncherClaudeStartPlanner(
        auto=False,
        resume=True,
        project_root=tmp_path / 'project',
        invocation_dir=tmp_path / 'invoke',
        platform_name='linux',
        env={},
        which_fn=lambda cmd: '/usr/bin/claude',
        get_latest_session_fn=lambda: (None, False, None),
    )

    plan = planner.build_plan()

    assert plan.cmd == ['/usr/bin/claude']
    assert plan.run_cwd == str(tmp_path / 'project')
    assert plan.has_history is False


def test_claude_start_planner_prefers_windows_npm_fallback(tmp_path: Path) -> None:
    appdata = tmp_path / 'AppData'
    npm_cmd = appdata / 'npm' / 'claude.cmd'
    npm_cmd.parent.mkdir(parents=True)
    npm_cmd.write_text('@echo off\r\n', encoding='utf-8')

    planner = LauncherClaudeStartPlanner(
        auto=False,
        resume=False,
        project_root=tmp_path / 'project',
        invocation_dir=tmp_path / 'invoke',
        platform_name='win32',
        env={'APPDATA': str(appdata), 'ProgramFiles': str(tmp_path / 'Program Files')},
        which_fn=lambda cmd: None,
        get_latest_session_fn=lambda: (None, False, None),
    )

    assert planner.find_claude_cmd() == str(npm_cmd)


def test_claude_start_planner_raises_when_cli_missing(tmp_path: Path) -> None:
    planner = LauncherClaudeStartPlanner(
        auto=False,
        resume=False,
        project_root=tmp_path / 'project',
        invocation_dir=tmp_path / 'invoke',
        platform_name='linux',
        env={},
        which_fn=lambda cmd: None,
        get_latest_session_fn=lambda: (None, False, None),
    )

    with pytest.raises(FileNotFoundError):
        planner.build_plan()
