from __future__ import annotations

from pathlib import Path

from launcher.tmux_helpers import choose_tmux_split_target, label_tmux_pane, spawn_tmux_pane


class _FakeBackend:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def get_current_pane_id(self) -> str:
        return '%1'

    def pane_exists(self, pane_id: str) -> bool:
        return pane_id != '%dead'

    def create_pane(self, cmd: str, cwd: str, direction: str = 'right', percent: int = 50, parent_pane: str | None = None) -> str:
        self.calls.append(('create', cmd, cwd, direction, percent, parent_pane))
        return '%9'

    def respawn_pane(self, pane_id: str, *, cmd: str, cwd: str | None = None, remain_on_exit: bool = True) -> None:
        self.calls.append(('respawn', pane_id, cmd, cwd, remain_on_exit))

    def set_pane_title(self, pane_id: str, title: str) -> None:
        self.calls.append(('title', pane_id, title))

    def set_pane_user_option(self, pane_id: str, name: str, value: str) -> None:
        self.calls.append(('option', pane_id, name, value))


def test_choose_tmux_split_target_falls_back_to_live_current_pane() -> None:
    backend = _FakeBackend()

    direction, parent = choose_tmux_split_target(
        backend,
        existing_panes={'codex': '%dead'},
        direction='bottom',
        parent_pane='%dead',
    )

    assert direction == 'bottom'
    assert parent == '%1'


def test_spawn_tmux_pane_respawns_and_labels() -> None:
    backend = _FakeBackend()

    pane_id = spawn_tmux_pane(
        backend,
        cwd=Path('/tmp/repo'),
        cmd='codex',
        title='CCB-Codex',
        agent_label='Codex',
        existing_panes={},
        direction=None,
        parent_pane=None,
    )

    assert pane_id == '%9'
    assert backend.calls[0] == ('create', '', '/tmp/repo', 'right', 50, '%1')
    assert backend.calls[1] == ('respawn', '%9', 'codex', '/tmp/repo', True)
    assert backend.calls[2] == ('title', '%9', 'CCB-Codex')
    assert backend.calls[3] == ('option', '%9', '@ccb_agent', 'Codex')


def test_label_tmux_pane_sets_title_and_agent_marker() -> None:
    backend = _FakeBackend()

    label_tmux_pane(backend, '%7', title='CCB-Claude', agent_label='Claude')

    assert backend.calls == [
        ('title', '%7', 'CCB-Claude'),
        ('option', '%7', '@ccb_agent', 'Claude'),
    ]
