from __future__ import annotations

from pathlib import Path

from launcher.target_tmux_launcher import LauncherTargetTmuxStarter


def test_target_tmux_starter_delegates_and_prints_started_message(tmp_path: Path) -> None:
    calls: dict[str, object] = {}
    printed: list[str] = []

    def _start_simple_target(**kwargs):
        calls['kwargs'] = kwargs
        return '%6'

    starter = LauncherTargetTmuxStarter(
        start_simple_target_fn=_start_simple_target,
        print_fn=printed.append,
    )

    pane_id = starter.start(
        target_key='gemini',
        display_label='Gemini',
        runtime=tmp_path / 'runtime',
        cwd=tmp_path,
        start_cmd='gemini --continue',
        pane_title_marker='CCB-Gemini',
        agent_label='Gemini',
        parent_pane='%1',
        direction='bottom',
        write_session_fn=lambda *args, **kwargs: True,
        started_backend_text='started {label} {pane_id}',
    )

    assert pane_id == '%6'
    assert calls['kwargs']['target_key'] == 'gemini'
    assert printed == ['started Gemini %6']
