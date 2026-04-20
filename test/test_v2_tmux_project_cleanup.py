from __future__ import annotations

import cli.services.tmux_project_cleanup as tmux_project_cleanup


def test_kill_project_tmux_panes_kills_current_pane_last(monkeypatch) -> None:
    calls: list[tuple[str | None, str]] = []

    class FakeTmuxBackend:
        def __init__(self, *, socket_name: str | None = None) -> None:
            self.socket_name = socket_name

        def list_panes_by_user_options(self, expected: dict[str, str]) -> list[str]:
            assert expected == {'@ccb_project_id': 'proj-1'}
            return ['%2', '%1', '%2', '%3']

        def kill_tmux_pane(self, pane_id: str) -> None:
            calls.append((self.socket_name, pane_id))

    monkeypatch.setattr(tmux_project_cleanup.shutil, 'which', lambda name: '/usr/bin/tmux')
    monkeypatch.setenv('TMUX_PANE', '%1')

    killed = tmux_project_cleanup.kill_project_tmux_panes(project_id='proj-1', backend_factory=FakeTmuxBackend)

    assert killed == ('%2', '%3', '%1')
    assert calls == [(None, '%2'), (None, '%3'), (None, '%1')]


def test_kill_project_tmux_panes_returns_empty_without_tmux(monkeypatch) -> None:
    monkeypatch.setattr(tmux_project_cleanup.shutil, 'which', lambda name: None)

    assert tmux_project_cleanup.kill_project_tmux_panes(project_id='proj-1') == ()


def test_cleanup_project_tmux_orphans_preserves_active_panes(monkeypatch) -> None:
    calls: list[tuple[str | None, str]] = []

    class FakeTmuxBackend:
        def __init__(self, *, socket_name: str | None = None) -> None:
            self.socket_name = socket_name

        def list_panes_by_user_options(self, expected: dict[str, str]) -> list[str]:
            assert expected == {'@ccb_project_id': 'proj-1'}
            return ['%2', '%1', '%3', '%2']

        def kill_tmux_pane(self, pane_id: str) -> None:
            calls.append((self.socket_name, pane_id))

    monkeypatch.setattr(tmux_project_cleanup.shutil, 'which', lambda name: '/usr/bin/tmux')
    monkeypatch.setenv('TMUX_PANE', '%3')

    killed = tmux_project_cleanup.cleanup_project_tmux_orphans(
        project_id='proj-1',
        active_panes=('%1',),
        socket_name='sock-a',
        backend_factory=FakeTmuxBackend,
    )

    assert killed == ('%2', '%3')
    assert calls == [('sock-a', '%2'), ('sock-a', '%3')]


def test_cleanup_project_tmux_orphans_by_socket_groups_servers(monkeypatch) -> None:
    calls: list[tuple[str | None, str]] = []

    class FakeTmuxBackend:
        def __init__(self, *, socket_name: str | None = None) -> None:
            self.socket_name = socket_name

        def list_panes_by_user_options(self, expected: dict[str, str]) -> list[str]:
            assert expected == {'@ccb_project_id': 'proj-1'}
            if self.socket_name == 'sock-a':
                return ['%1', '%2']
            if self.socket_name == 'sock-b':
                return ['%8']
            return []

        def kill_tmux_pane(self, pane_id: str) -> None:
            calls.append((self.socket_name, pane_id))

    monkeypatch.setattr(tmux_project_cleanup.shutil, 'which', lambda name: '/usr/bin/tmux')

    summaries = tmux_project_cleanup.cleanup_project_tmux_orphans_by_socket(
        project_id='proj-1',
        active_panes_by_socket={'sock-a': ('%1',), 'sock-b': ('%8',)},
        backend_factory=FakeTmuxBackend,
    )

    assert [item.socket_name for item in summaries] == ['sock-a', 'sock-b']
    assert summaries[0].orphaned_panes == ('%2',)
    assert summaries[0].killed_panes == ('%2',)
    assert summaries[1].orphaned_panes == ()
    assert summaries[1].killed_panes == ()
    assert calls == [('sock-a', '%2')]


def test_cleanup_project_tmux_orphans_by_socket_accepts_socket_paths(monkeypatch, tmp_path) -> None:
    socket_path = tmp_path / 'project.sock'
    calls: list[tuple[str | None, str | None, str]] = []

    class FakeTmuxBackend:
        def __init__(self, *, socket_name: str | None = None, socket_path: str | None = None) -> None:
            self.socket_name = socket_name
            self.socket_path = socket_path

        def list_panes_by_user_options(self, expected: dict[str, str]) -> list[str]:
            assert expected == {'@ccb_project_id': 'proj-1'}
            assert self.socket_name is None
            assert self.socket_path == str(socket_path)
            return ['%1', '%2']

        def kill_tmux_pane(self, pane_id: str) -> None:
            calls.append((self.socket_name, self.socket_path, pane_id))

    monkeypatch.setattr(tmux_project_cleanup.shutil, 'which', lambda name: '/usr/bin/tmux')

    summaries = tmux_project_cleanup.cleanup_project_tmux_orphans_by_socket(
        project_id='proj-1',
        active_panes_by_socket={str(socket_path): ('%1',)},
        backend_factory=FakeTmuxBackend,
    )

    assert [item.socket_name for item in summaries] == [str(socket_path)]
    assert summaries[0].orphaned_panes == ('%2',)
    assert summaries[0].killed_panes == ('%2',)
    assert calls == [(None, str(socket_path), '%2')]
