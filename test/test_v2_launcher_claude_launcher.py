from __future__ import annotations

from launcher.claude_launcher import LauncherClaudePaneLauncher


class _FakeTmuxBackend:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def create_pane(self, cmd: str, cwd: str, direction: str = 'right', percent: int = 50, parent_pane: str | None = None) -> str:
        self.calls.append(('create', cmd, cwd, direction, percent, parent_pane))
        return '%3'

    def respawn_pane(self, pane_id: str, *, cmd: str, cwd: str | None = None, remain_on_exit: bool = True) -> None:
        self.calls.append(('respawn', pane_id, cmd, cwd, remain_on_exit))


def test_claude_launcher_starts_tmux_pane_and_writes_local_session() -> None:
    tmux_backend = _FakeTmuxBackend()
    calls: dict[str, object] = {}
    launcher = LauncherClaudePaneLauncher(
        script_dir='/tmp/repo',
        tmux_panes={},
        build_env_prefix_fn=lambda env: 'export CLAUDE=1; ',
        export_path_builder_fn=lambda path: 'export PATH=/tmp/repo/bin; ',
        pane_title_builder_fn=lambda title: 'title:CCB-Claude; ',
        tmux_backend_factory=lambda: tmux_backend,
        label_tmux_pane_fn=lambda backend, pane_id, *, title, agent_label: calls.__setitem__('label', (pane_id, title, agent_label)),
    )

    pane_id = launcher.start(
        run_cwd='/tmp/repo',
        start_cmd='claude --continue',
        env_overrides={'CCB_CALLER': 'claude'},
        write_local_session_fn=lambda **kwargs: calls.__setitem__('session', kwargs),
        read_local_session_id_fn=lambda: 'claude-sess-1',
        parent_pane='%1',
        direction='bottom',
        display_label='reviewer',
    )

    assert pane_id == '%3'
    assert tmux_backend.calls[0] == ('create', '', '/tmp/repo', 'bottom', 50, '%1')
    assert tmux_backend.calls[1][0] == 'respawn'
    assert calls['label'] == ('%3', 'CCB-reviewer', 'reviewer')
    assert calls['session']['session_id'] == 'claude-sess-1'
    assert calls['session']['pane_id'] == '%3'
    assert calls['session']['pane_title_marker'] == 'CCB-reviewer'
