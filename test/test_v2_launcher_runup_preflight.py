from __future__ import annotations

from io import StringIO

from launcher.runup_preflight import LauncherRunUpPreflight


def test_runup_preflight_builds_anchor_and_layout(monkeypatch) -> None:
    monkeypatch.setenv('TMUX', '/tmp/tmux-1000/default,1,0')
    preflight = LauncherRunUpPreflight(
        target_names=('gemini', 'codex'),
        terminal_type='tmux',
        require_project_config_dir_fn=lambda: True,
        backfill_claude_session_fn=lambda: None,
        current_pane_id_fn=lambda: '%1',
        cmd_settings_fn=lambda: {'enabled': True},
        translate_fn=lambda key, **kwargs: key,
        stderr=StringIO(),
    )

    result = preflight.prepare()

    assert result.code is None
    assert result.terminal_type == 'tmux'
    assert result.anchor_name == 'codex'
    assert result.anchor_pane_id == '%1'
    assert result.cmd_settings == {'enabled': True}
    assert result.layout is not None
    assert result.layout.left_items == ('codex',)
    assert result.layout.right_items == ('cmd', 'gemini')


def test_runup_preflight_reports_missing_terminal(monkeypatch) -> None:
    stderr = StringIO()
    monkeypatch.delenv('TMUX', raising=False)
    monkeypatch.delenv('TMUX_PANE', raising=False)
    preflight = LauncherRunUpPreflight(
        target_names=('codex',),
        terminal_type='tmux',
        require_project_config_dir_fn=lambda: True,
        backfill_claude_session_fn=lambda: None,
        current_pane_id_fn=lambda: '%1',
        cmd_settings_fn=lambda: {'enabled': False},
        translate_fn=lambda key, **kwargs: key,
        stderr=stderr,
    )

    result = preflight.prepare()

    assert result.code == 2
    assert result.terminal_type is None
    assert 'no_terminal_backend' in stderr.getvalue()


def test_runup_preflight_requires_anchor_pane(monkeypatch) -> None:
    stderr = StringIO()
    monkeypatch.setenv('TMUX', '/tmp/tmux-1000/default,1,0')
    preflight = LauncherRunUpPreflight(
        target_names=('codex',),
        terminal_type='tmux',
        require_project_config_dir_fn=lambda: True,
        backfill_claude_session_fn=lambda: None,
        current_pane_id_fn=lambda: '',
        cmd_settings_fn=lambda: {'enabled': False},
        translate_fn=lambda key, **kwargs: key,
        stderr=stderr,
    )

    result = preflight.prepare()

    assert result.code == 2
    assert 'Unable to determine current pane id' in stderr.getvalue()
