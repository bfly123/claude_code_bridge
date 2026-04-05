from __future__ import annotations

from launcher.cmd_pane_launcher import LauncherCmdPaneLauncher


class _FakeTmuxBackend:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def create_pane(self, cmd: str, cwd: str, direction: str = 'right', percent: int = 50, parent_pane: str | None = None) -> str:
        self.calls.append(('create', cmd, cwd, direction, percent, parent_pane))
        return '%5'

    def respawn_pane(self, pane_id: str, *, cmd: str, cwd: str | None = None, remain_on_exit: bool = True) -> None:
        self.calls.append(('respawn', pane_id, cmd, cwd, remain_on_exit))


def test_cmd_pane_launcher_starts_tmux_and_labels_pane() -> None:
    extra_panes: dict[str, str] = {}
    labels: list[tuple] = []
    printed: list[str] = []
    backend = _FakeTmuxBackend()
    launcher = LauncherCmdPaneLauncher(
        extra_panes=extra_panes,
        backend_factory=lambda: backend,
        label_tmux_pane_fn=lambda tmux_backend, pane_id, *, title, agent_label: labels.append((pane_id, title, agent_label)),
        print_fn=printed.append,
    )

    pane_id = launcher.start(
        title='CCB-Cmd',
        full_cmd='echo hi',
        cwd='/tmp/demo',
        parent_pane='%1',
        direction='bottom',
    )

    assert pane_id == '%5'
    assert backend.calls[0] == ('create', '', '/tmp/demo', 'bottom', 50, '%1')
    assert backend.calls[1] == ('respawn', '%5', 'echo hi', '/tmp/demo', True)
    assert labels == [('%5', 'CCB-Cmd', 'Cmd')]
    assert extra_panes['cmd'] == '%5'
    assert printed == ['✅ Started cmd pane (%5)']
