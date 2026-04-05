from __future__ import annotations

from io import StringIO
from pathlib import Path

from launcher.current_target_launcher import LauncherCurrentTargetLauncher


def test_current_target_launcher_starts_shell_provider(tmp_path: Path) -> None:
    bind_calls: list[dict] = []
    run_calls: list[tuple[str, str]] = []
    launcher = LauncherCurrentTargetLauncher(
        bind_current_pane_fn=lambda **kwargs: bind_calls.append(kwargs) or '%9',
    )

    rc = launcher.start_shell_target(
        runtime=tmp_path / 'runtime',
        pane_title_marker='CCB-Gemini',
        agent_label='Gemini',
        display_label='Gemini',
        bind_session_fn=lambda pane_id: True,
        start_cmd='gemini --continue',
        run_shell_command_fn=lambda cmd, cwd=None, **kwargs: run_calls.append((cmd, cwd)) or 0,
        cwd='/tmp/work',
    )

    assert rc == 0
    assert bind_calls[0]['pane_title_marker'] == 'CCB-Gemini'
    assert run_calls == [('gemini --continue', '/tmp/work')]


def test_current_target_launcher_reports_missing_pane(tmp_path: Path) -> None:
    stderr = StringIO()
    launcher = LauncherCurrentTargetLauncher(
        bind_current_pane_fn=lambda **kwargs: None,
        stderr=stderr,
    )

    rc = launcher.start_shell_target(
        runtime=tmp_path / 'runtime',
        pane_title_marker='CCB-Droid',
        agent_label='Droid',
        display_label='Droid',
        bind_session_fn=lambda pane_id: True,
        start_cmd='droid',
        run_shell_command_fn=lambda cmd, cwd=None, **kwargs: 0,
        cwd='/tmp/work',
    )

    assert rc == 1
    assert 'Unable to determine current pane id for Droid' in stderr.getvalue()
