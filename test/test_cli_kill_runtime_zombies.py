from __future__ import annotations

import cli.kill_runtime.zombies as zombies


def test_find_all_zombie_sessions_filters_dead_parents() -> None:
    result = zombies.find_all_zombie_sessions(
        is_pid_alive=lambda pid: pid == 456,
        list_tmux_sessions_fn=lambda: [
            'codex-123-worker',
            'claude-456-run',
            'demo-other',
        ],
    )

    assert result == [
        {
            'session': 'codex-123-worker',
            'provider': 'codex',
            'parent_pid': 123,
        }
    ]


def test_kill_global_zombies_reports_partial_failures(capsys) -> None:
    code = zombies.kill_global_zombies(
        yes=True,
        is_pid_alive=lambda pid: False,
        find_all_zombie_sessions_fn=lambda **kwargs: [
            {'session': 'codex-123-worker', 'provider': 'codex', 'parent_pid': 123},
            {'session': 'claude-234-run', 'provider': 'claude', 'parent_pid': 234},
        ],
        kill_tmux_session_fn=lambda name: name == 'codex-123-worker',
    )

    assert code == 0
    out = capsys.readouterr().out
    assert 'Found 2 zombie session(s):' in out
    assert 'Cleaned up 1 zombie session(s), 1 failed' in out
