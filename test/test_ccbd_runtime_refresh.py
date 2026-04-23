from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from agents.models import AgentRuntime, AgentState, RuntimeBindingSource
from ccbd.services.project_namespace_runtime.slot_replacement import ProjectSlotRecoveryContext
from ccbd.services.runtime_runtime.refresh import refresh_provider_binding
from provider_backends.pane_log_support.session import PaneLogProjectSessionBase
from provider_core.contracts import ProviderSessionBinding
from storage.paths import PathLayout


class _Registry:
    def __init__(self, runtime: AgentRuntime) -> None:
        self._runtime = runtime
        self._config = SimpleNamespace(default_agents=('agent1',))

    def get(self, agent_name: str):
        assert agent_name == 'agent1'
        return self._runtime

    def spec_for(self, agent_name: str):
        assert agent_name == 'agent1'
        return SimpleNamespace(name='agent1', provider='codex')


class _FakeBackend:
    def __init__(self) -> None:
        self._socket_path = '/tmp/project.sock'
        self.created: list[dict[str, object]] = []
        self.titles: list[tuple[str, str]] = []
        self.options: list[tuple[str, str, str]] = []
        self.styles: list[tuple[str, str | None, str | None]] = []

    def pane_exists(self, pane_id: str) -> bool:
        return pane_id in {'%root', '%55'}

    def is_alive(self, pane_id: str) -> bool:
        return pane_id in {'%root', '%55'}

    def create_pane(
        self,
        cmd: str,
        cwd: str,
        direction: str = 'right',
        percent: int = 50,
        parent_pane: str | None = None,
    ) -> str:
        self.created.append(
            {
                'cmd': cmd,
                'cwd': cwd,
                'direction': direction,
                'percent': percent,
                'parent_pane': parent_pane,
            }
        )
        return '%55'

    def set_pane_title(self, pane_id: str, title: str) -> None:
        self.titles.append((pane_id, title))

    def set_pane_user_option(self, pane_id: str, key: str, value: str) -> None:
        self.options.append((pane_id, key, value))

    def set_pane_style(
        self,
        pane_id: str,
        *,
        border_style: str | None = None,
        active_border_style: str | None = None,
    ) -> None:
        self.styles.append((pane_id, border_style, active_border_style))

    def ensure_pane_log(self, pane_id: str) -> None:
        return None


@dataclass
class _Session(PaneLogProjectSessionBase):
    _backend: object

    @property
    def fake_session_id(self) -> str:
        return str(self.data.get('fake_session_id') or '').strip()

    @property
    def fake_session_path(self) -> str:
        return str(self.data.get('fake_session_path') or '').strip()

    def backend(self):
        return self._backend


def _runtime(layout: PathLayout) -> AgentRuntime:
    return AgentRuntime(
        agent_name='agent1',
        state=AgentState.DEGRADED,
        pid=101,
        started_at='2026-04-01T00:00:00Z',
        last_seen_at='2026-04-01T00:00:01Z',
        runtime_ref='tmux:%41',
        session_ref='session-old',
        workspace_path=str(layout.workspace_path('agent1')),
        project_id='proj-1',
        backend_type='pane-backed',
        queue_depth=0,
        socket_path=None,
        health='pane-missing',
        provider='codex',
        terminal_backend='tmux',
        pane_id='%41',
        active_pane_id='%41',
        pane_state='missing',
        tmux_socket_path='/tmp/project.sock',
        slot_key='agent1',
        managed_by='ccbd',
        binding_source=RuntimeBindingSource.PROVIDER_SESSION,
    )


def test_refresh_provider_binding_replaces_missing_project_pane_inside_workspace(monkeypatch, tmp_path: Path) -> None:
    layout = PathLayout(tmp_path / 'repo-refresh')
    runtime = _runtime(layout)
    runtime.runtime_root = '/tmp/runtime-root'
    runtime.runtime_pid = 456
    runtime.lifecycle_state = 'degraded'
    runtime.managed_by = 'ccbd'
    registry = _Registry(runtime)
    backend = _FakeBackend()
    session_file = layout.ccb_dir / 'agent1.session.json'
    session_file.parent.mkdir(parents=True, exist_ok=True)
    session_file.write_text('{}\n', encoding='utf-8')
    session = _Session(
        session_file=session_file,
        data={
            'terminal': 'tmux',
            'pane_id': '%41',
            'agent_name': 'agent1',
            'ccb_project_id': 'proj-1',
            'work_dir': str(layout.workspace_path('agent1')),
            'start_cmd': 'codex --continue',
            'fake_session_id': 'session-new',
            'job_id': 'job-object-1',
            'job_owner_pid': '654',
        },
        _backend=backend,
    )
    replacement_context = ProjectSlotRecoveryContext(
        project_id='proj-1',
        slot_key='agent1',
        tmux_socket_path='/tmp/project.sock',
        tmux_session_name='ccb-demo',
        namespace_epoch=4,
        workspace_window_name='ccb',
        workspace_window_id='@2',
        workspace_epoch=3,
        workspace_root_pane_id='%root',
        style_index=0,
    )
    binding = ProviderSessionBinding(
        provider='codex',
        load_session=lambda workspace_path, instance: session,
        session_id_attr='fake_session_id',
        session_path_attr='fake_session_path',
    )
    attached: list[dict[str, object]] = []

    monkeypatch.setattr(
        'ccbd.services.runtime_runtime.refresh.resolve_project_slot_recovery_context',
        lambda **kwargs: replacement_context,
    )
    monkeypatch.setattr(
        'ccbd.services.project_namespace_runtime.slot_replacement.TmuxBackend',
        lambda socket_path=None: backend,
    )

    refreshed = refresh_provider_binding(
        layout=layout,
        registry=registry,
        session_bindings={'codex': binding},
        attach_runtime_fn=lambda **kwargs: attached.append(kwargs) or SimpleNamespace(**kwargs),
        agent_name='agent1',
        recover=True,
    )

    assert refreshed is not None
    assert backend.created == [
        {
            'cmd': 'codex --continue',
            'cwd': str(layout.workspace_path('agent1')),
            'direction': 'right',
            'percent': 50,
            'parent_pane': '%root',
        }
    ]
    assert attached[0]['pane_id'] == '%55'
    assert attached[0]['active_pane_id'] == '%55'
    assert attached[0]['slot_key'] == 'agent1'
    assert attached[0]['window_id'] == '@2'
    assert attached[0]['workspace_epoch'] == 3
    assert attached[0]['session_ref'] == 'session-new'
    assert attached[0]['runtime_root'] == str(layout.ccb_dir)
    assert attached[0]['runtime_pid'] == 456
    assert attached[0]['job_id'] == 'job-object-1'
    assert attached[0]['job_owner_pid'] == 654
    assert attached[0]['lifecycle_state'] == 'degraded'
    assert attached[0]['managed_by'] == 'ccbd'
    assert session.data['pane_id'] == '%55'
    assert ('%55', 'cmd') not in backend.titles
    assert ('%55', 'agent1') in backend.titles


def test_refresh_provider_binding_preserves_runtime_job_metadata_when_session_is_missing(tmp_path: Path) -> None:
    layout = PathLayout(tmp_path / 'repo-refresh-missing')
    runtime = _runtime(layout)
    runtime.provider = 'codex'
    runtime.runtime_root = '/tmp/runtime-root'
    runtime.runtime_pid = 456
    runtime.job_id = 'job-object-1'
    runtime.job_owner_pid = 654
    runtime.terminal_backend = 'psmux'
    runtime.pane_title_marker = 'agent1'
    runtime.tmux_socket_name = 'psmux-agent1'
    registry = _Registry(runtime)
    binding = ProviderSessionBinding(
        provider='codex',
        load_session=lambda workspace_path, instance: None,
        session_id_attr='fake_session_id',
        session_path_attr='fake_session_path',
    )
    attached: list[dict[str, object]] = []

    refreshed = refresh_provider_binding(
        layout=layout,
        registry=registry,
        session_bindings={'codex': binding},
        attach_runtime_fn=lambda **kwargs: attached.append(kwargs) or SimpleNamespace(**kwargs),
        agent_name='agent1',
        recover=False,
    )

    assert refreshed is not None
    assert attached[0]['health'] == 'session-missing'
    assert attached[0]['provider'] == 'codex'
    assert attached[0]['runtime_root'] == '/tmp/runtime-root'
    assert attached[0]['runtime_pid'] == 456
    assert attached[0]['job_id'] == 'job-object-1'
    assert attached[0]['job_owner_pid'] == 654
    assert attached[0]['terminal_backend'] == 'psmux'
    assert attached[0]['pane_id'] == '%41'
    assert attached[0]['active_pane_id'] == '%41'
    assert attached[0]['pane_title_marker'] == 'agent1'
    assert attached[0]['pane_state'] == 'missing'
    assert attached[0]['tmux_socket_name'] == 'psmux-agent1'
    assert attached[0]['tmux_socket_path'] == '/tmp/project.sock'
    assert attached[0]['lifecycle_state'] == 'degraded'
    assert attached[0]['managed_by'] == 'ccbd'


def test_refresh_provider_binding_collects_psmux_socket_from_session_backend(tmp_path: Path) -> None:
    layout = PathLayout(tmp_path / 'repo-refresh-psmux')
    runtime = _runtime(layout)
    runtime.runtime_root = '/tmp/runtime-root'
    runtime.job_id = 'job-object-1'
    runtime.job_owner_pid = 654
    runtime.lifecycle_state = 'degraded'
    runtime.managed_by = 'ccbd'
    runtime.pane_title_marker = 'agent1'
    runtime.tmux_socket_path = None
    registry = _Registry(runtime)
    session_file = layout.ccb_dir / 'agent1.psmux.session.json'
    session_file.parent.mkdir(parents=True, exist_ok=True)
    session_file.write_text('{}\n', encoding='utf-8')
    session = _Session(
        session_file=session_file,
        data={
            'terminal': 'psmux',
            'pane_id': '%41',
            'agent_name': 'agent1',
            'ccb_project_id': 'proj-1',
            'fake_session_id': 'session-psmux',
            'runtime_pid': '999',
        },
        _backend=SimpleNamespace(_socket_name='psmux-sock', _socket_path=r'\\.\pipe\psmux-agent1'),
    )
    binding = ProviderSessionBinding(
        provider='codex',
        load_session=lambda workspace_path, instance: session,
        session_id_attr='fake_session_id',
        session_path_attr='fake_session_path',
    )
    attached: list[dict[str, object]] = []

    refreshed = refresh_provider_binding(
        layout=layout,
        registry=registry,
        session_bindings={'codex': binding},
        attach_runtime_fn=lambda **kwargs: attached.append(kwargs) or SimpleNamespace(**kwargs),
        agent_name='agent1',
        recover=False,
    )

    assert refreshed is not None
    assert attached[0]['session_ref'] == 'session-psmux'
    assert attached[0]['session_id'] == 'session-psmux'
    assert attached[0]['session_file'] == str(session_file)
    assert attached[0]['terminal_backend'] == 'psmux'
    assert attached[0]['runtime_pid'] == 999
    assert attached[0]['runtime_root'] == str(layout.ccb_dir)
    assert attached[0]['job_id'] == 'job-object-1'
    assert attached[0]['job_owner_pid'] == 654
    assert attached[0]['lifecycle_state'] == 'degraded'
    assert attached[0]['managed_by'] == 'ccbd'
    assert attached[0]['pane_title_marker'] == 'agent1'
    assert attached[0]['tmux_socket_name'] == 'psmux-sock'
    assert attached[0]['tmux_socket_path'] == r'\\.\pipe\psmux-agent1'


def test_resolve_project_slot_recovery_context_uses_generic_namespace_aliases(monkeypatch, tmp_path: Path) -> None:
    from ccbd.services.project_namespace_runtime import slot_replacement as slot_replacement_module

    layout = PathLayout(tmp_path / 'repo-refresh-generic-alias')
    runtime = _runtime(layout)
    runtime.tmux_socket_path = r'\\.\pipe\psmux-slot'

    class _Controller:
        def __init__(self, layout_arg, project_id_arg) -> None:
            assert layout_arg == layout
            assert project_id_arg == 'proj-1'

        def load(self):
            return SimpleNamespace(
                ui_attachable=True,
                backend_ref=r'\\.\pipe\psmux-slot',
                session_name='ccb-psmux',
                workspace_name='workspace-psmux',
                workspace_window_id='@7',
                workspace_epoch=6,
                namespace_epoch=8,
            )

        def root_pane_id(self, namespace) -> str:
            assert namespace.backend_ref == r'\\.\pipe\psmux-slot'
            assert namespace.session_name == 'ccb-psmux'
            assert namespace.workspace_name == 'workspace-psmux'
            return '%root'

    monkeypatch.setattr(slot_replacement_module, 'ProjectNamespaceController', _Controller)

    context = slot_replacement_module.resolve_project_slot_recovery_context(
        layout=layout,
        config=SimpleNamespace(default_agents=('agent1',)),
        runtime=runtime,
        agent_name='agent1',
    )

    assert context == ProjectSlotRecoveryContext(
        project_id='proj-1',
        slot_key='agent1',
        tmux_socket_path=r'\\.\pipe\psmux-slot',
        tmux_session_name='ccb-psmux',
        namespace_epoch=8,
        workspace_window_name='workspace-psmux',
        workspace_window_id='@7',
        workspace_epoch=6,
        workspace_root_pane_id='%root',
        style_index=0,
    )

