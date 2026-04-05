from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

from ccbd.services.project_namespace import ProjectNamespaceController
from ccbd.services.project_namespace_state import (
    ProjectNamespaceEvent,
    ProjectNamespaceEventStore,
    ProjectNamespaceState,
    ProjectNamespaceStateStore,
)
from storage.paths import PathLayout


def test_project_namespace_state_store_round_trip(tmp_path: Path) -> None:
    layout = PathLayout(tmp_path / 'repo')
    state = ProjectNamespaceState(
        project_id='proj-1',
        namespace_epoch=3,
        tmux_socket_path=str(layout.ccbd_tmux_socket_path),
        tmux_session_name=layout.ccbd_tmux_session_name,
        layout_version=2,
        layout_signature='cmd; agent1:codex',
        ui_attachable=True,
        last_started_at='2026-04-03T01:00:00Z',
        last_destroyed_at='2026-04-03T00:55:00Z',
        last_destroy_reason='kill',
    )

    store = ProjectNamespaceStateStore(layout)
    store.save(state)
    loaded = store.load()

    assert loaded == state
    assert loaded is not None
    assert loaded.summary_fields()['namespace_tmux_socket_path'] == str(layout.ccbd_tmux_socket_path)


@dataclass
class _FakeTmuxBackend:
    socket_path: str | None = None
    sessions: dict[str, list[str]] = field(default_factory=dict)
    pane_titles: dict[str, str] = field(default_factory=dict)
    pane_options: dict[str, dict[str, str]] = field(default_factory=dict)
    session_options: dict[str, dict[str, str]] = field(default_factory=dict)
    window_options: dict[str, dict[str, str]] = field(default_factory=dict)
    hooks: dict[str, dict[str, str]] = field(default_factory=dict)
    tmux_calls: list[tuple[list[str], bool]] = field(default_factory=list)
    pane_counter: int = 0
    server_killed: bool = False

    def _tmux_run(
        self,
        args: list[str],
        *,
        check: bool = False,
        capture: bool = False,
        input_bytes: bytes | None = None,
        timeout: float | None = None,
    ):
        del check, input_bytes, timeout
        self.tmux_calls.append((list(args), capture))
        if args[:1] == ['start-server']:
            return SimpleNamespace(returncode=0, stdout='', stderr='')
        if args[:3] == ['set-option', '-g', 'destroy-unattached']:
            return SimpleNamespace(returncode=0, stdout='', stderr='')
        if len(args) >= 3 and args[:2] == ['has-session', '-t']:
            return SimpleNamespace(returncode=0 if args[2] in self.sessions else 1, stdout='', stderr='')
        if len(args) >= 9 and args[:2] == ['new-session', '-d']:
            session_name = args[7]
            self.pane_counter += 1
            pane_id = f'%{self.pane_counter}'
            self.sessions[session_name] = [pane_id]
            return SimpleNamespace(returncode=0, stdout='', stderr='')
        if len(args) >= 4 and args[:2] == ['list-panes', '-t']:
            session_name = args[2]
            panes = self.sessions.get(session_name, [])
            if capture and len(args) >= 5 and args[4] == '#{?pane_active,#{pane_id},}':
                active = panes[0] if panes else ''
                return SimpleNamespace(returncode=0, stdout=f'{active}\n', stderr='')
            return SimpleNamespace(returncode=0, stdout='\n'.join(panes), stderr='')
        if len(args) >= 5 and args[:2] == ['set-option', '-t']:
            self.session_options.setdefault(args[2], {})[args[3]] = args[4]
            return SimpleNamespace(returncode=0, stdout='', stderr='')
        if len(args) >= 5 and args[:2] == ['set-window-option', '-t']:
            self.window_options.setdefault(args[2], {})[args[3]] = args[4]
            return SimpleNamespace(returncode=0, stdout='', stderr='')
        if len(args) >= 5 and args[:2] == ['set-hook', '-t']:
            self.hooks.setdefault(args[2], {})[args[3]] = args[4]
            return SimpleNamespace(returncode=0, stdout='', stderr='')
        if len(args) >= 6 and args[:3] == ['set-option', '-p', '-t']:
            self.pane_options.setdefault(args[3], {})[args[4]] = args[5]
            return SimpleNamespace(returncode=0, stdout='', stderr='')
        if len(args) >= 5 and args[:3] == ['display-message', '-p', '-t']:
            pane_id = args[3]
            fmt = args[4]
            if fmt == '#{@ccb_active_border_style}':
                value = self.pane_options.get(pane_id, {}).get('@ccb_active_border_style', '')
                return SimpleNamespace(returncode=0, stdout=f'{value}\n', stderr='')
            if fmt == '#{@ccb_border_style}':
                value = self.pane_options.get(pane_id, {}).get('@ccb_border_style', '')
                return SimpleNamespace(returncode=0, stdout=f'{value}\n', stderr='')
            return SimpleNamespace(returncode=0, stdout='', stderr='')
        if args[:1] == ['kill-server']:
            self.server_killed = True
            self.sessions.clear()
            return SimpleNamespace(returncode=0, stdout='', stderr='')
        raise AssertionError(f'unexpected tmux args: {args}')

    def is_alive(self, session_name: str) -> bool:
        return session_name in self.sessions

    def set_pane_title(self, pane_id: str, title: str) -> None:
        self.pane_titles[pane_id] = title

    def set_pane_user_option(self, pane_id: str, name: str, value: str) -> None:
        self.pane_options.setdefault(pane_id, {})[name] = value

    def set_pane_style(
        self,
        pane_id: str,
        *,
        border_style: str | None = None,
        active_border_style: str | None = None,
    ) -> None:
        options = self.pane_options.setdefault(pane_id, {})
        if border_style:
            options['pane-border-style'] = border_style
        if active_border_style:
            options['pane-active-border-style'] = active_border_style


def test_project_namespace_controller_creates_state_and_lifecycle_event(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo'
    layout = PathLayout(project_root)
    backend = _FakeTmuxBackend()
    controller = ProjectNamespaceController(
        layout,
        'proj-1',
        clock=lambda: '2026-04-03T02:00:00Z',
        backend_factory=lambda socket_path=None: backend,
    )

    namespace = controller.ensure()
    state = ProjectNamespaceStateStore(layout).load()
    latest_event = ProjectNamespaceEventStore(layout).load_latest()

    assert namespace.project_id == 'proj-1'
    assert namespace.namespace_epoch == 1
    assert state is not None
    assert state.tmux_socket_path == str(layout.ccbd_tmux_socket_path)
    assert state.tmux_session_name == layout.ccbd_tmux_session_name
    assert backend.sessions[layout.ccbd_tmux_session_name] == ['%1']
    assert backend.pane_titles['%1'] == 'cmd'
    assert backend.pane_options['%1']['@ccb_slot'] == 'cmd'
    assert backend.pane_options['%1']['@ccb_namespace_epoch'] == '1'
    assert backend.pane_options['%1']['@ccb_managed_by'] == 'ccbd'
    assert backend.window_options[layout.ccbd_tmux_session_name]['pane-border-status'] == 'top'
    assert 'after-select-pane' in backend.hooks[layout.ccbd_tmux_session_name]
    assert latest_event is not None
    assert latest_event.event_kind == 'namespace_created'
    assert latest_event.details['recreated'] is False
    assert latest_event.details['reason'] == 'initial_create'


def test_project_namespace_controller_recreates_missing_session_with_new_epoch(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-recreate'
    layout = PathLayout(project_root)
    backend = _FakeTmuxBackend()
    controller = ProjectNamespaceController(
        layout,
        'proj-2',
        clock=lambda: '2026-04-03T03:00:00Z',
        backend_factory=lambda socket_path=None: backend,
    )

    first = controller.ensure()
    backend.sessions.clear()
    second = controller.ensure()
    latest_event = ProjectNamespaceEventStore(layout).load_latest()

    assert first.namespace_epoch == 1
    assert second.namespace_epoch == 2
    assert latest_event is not None
    assert latest_event.event_kind == 'namespace_created'
    assert latest_event.namespace_epoch == 2
    assert latest_event.details['recreated'] is True
    assert latest_event.details['reason'] == 'missing_session'


def test_project_namespace_controller_recreates_session_when_layout_version_changes(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-layout-upgrade'
    layout = PathLayout(project_root)
    backend = _FakeTmuxBackend()
    state_store = ProjectNamespaceStateStore(layout)
    state_store.save(
        ProjectNamespaceState(
            project_id='proj-5',
            namespace_epoch=4,
            tmux_socket_path=str(layout.ccbd_tmux_socket_path),
            tmux_session_name=layout.ccbd_tmux_session_name,
            layout_version=1,
            layout_signature='cmd; agent1:codex',
            ui_attachable=True,
        )
    )
    backend.sessions[layout.ccbd_tmux_session_name] = ['%8']
    controller = ProjectNamespaceController(
        layout,
        'proj-5',
        clock=lambda: '2026-04-03T06:00:00Z',
        backend_factory=lambda socket_path=None: backend,
        layout_version=2,
    )

    namespace = controller.ensure()
    latest_event = ProjectNamespaceEventStore(layout).load_latest()

    assert namespace.namespace_epoch == 5
    assert backend.server_killed is True
    assert backend.sessions[layout.ccbd_tmux_session_name] == ['%1']
    assert latest_event is not None
    assert latest_event.details['reason'] == 'layout_version_changed'


def test_project_namespace_controller_recreates_session_when_layout_signature_changes(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-layout-signature-upgrade'
    layout = PathLayout(project_root)
    backend = _FakeTmuxBackend()
    state_store = ProjectNamespaceStateStore(layout)
    state_store.save(
        ProjectNamespaceState(
            project_id='proj-6',
            namespace_epoch=7,
            tmux_socket_path=str(layout.ccbd_tmux_socket_path),
            tmux_session_name=layout.ccbd_tmux_session_name,
            layout_version=2,
            layout_signature='cmd; agent1:codex',
            ui_attachable=True,
        )
    )
    backend.sessions[layout.ccbd_tmux_session_name] = ['%9']
    controller = ProjectNamespaceController(
        layout,
        'proj-6',
        clock=lambda: '2026-04-03T07:00:00Z',
        backend_factory=lambda socket_path=None: backend,
        layout_version=2,
    )

    namespace = controller.ensure(layout_signature='cmd, agent1:codex; agent2:claude')
    latest_event = ProjectNamespaceEventStore(layout).load_latest()

    assert namespace.namespace_epoch == 8
    assert namespace.layout_signature == 'cmd, agent1:codex; agent2:claude'
    assert backend.server_killed is True
    assert backend.sessions[layout.ccbd_tmux_session_name] == ['%1']
    assert latest_event is not None
    assert latest_event.details['reason'] == 'layout_signature_changed'


def test_project_namespace_controller_destroy_marks_state_and_event(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-destroy'
    layout = PathLayout(project_root)
    backend = _FakeTmuxBackend()
    controller = ProjectNamespaceController(
        layout,
        'proj-3',
        clock=lambda: '2026-04-03T04:00:00Z',
        backend_factory=lambda socket_path=None: backend,
    )

    controller.ensure()
    summary = controller.destroy(reason='kill')
    state = ProjectNamespaceStateStore(layout).load()
    latest_event = ProjectNamespaceEventStore(layout).load_latest()

    assert summary.destroyed is True
    assert summary.reason == 'kill'
    assert backend.server_killed is True
    assert state is not None
    assert state.ui_attachable is False
    assert state.last_destroy_reason == 'kill'
    assert latest_event is not None
    assert latest_event.event_kind == 'namespace_destroyed'
    assert latest_event.details['reason'] == 'kill'


def test_project_namespace_controller_uses_silent_server_commands(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-silent'
    layout = PathLayout(project_root)
    backend = _FakeTmuxBackend()
    controller = ProjectNamespaceController(
        layout,
        'proj-4',
        clock=lambda: '2026-04-03T05:00:00Z',
        backend_factory=lambda socket_path=None: backend,
    )

    controller.ensure()
    controller.destroy(reason='kill')

    new_session_calls = [args for args, capture in backend.tmux_calls if args[:2] == ['new-session', '-d'] and capture is False]
    assert len(new_session_calls) == 1
    assert new_session_calls[0][-3:] == ['sh', '-lc', 'while :; do sleep 3600; done']
    assert (['start-server'], True) in backend.tmux_calls
    assert (['set-option', '-g', 'destroy-unattached', 'off'], True) in backend.tmux_calls
    assert (['kill-server'], True) in backend.tmux_calls
