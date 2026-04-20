from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from ccbd.start_runtime.binding import (
    declared_binding_tmux_socket_path,
    relabel_project_namespace_pane,
    usable_agent_only_project_binding,
    usable_project_namespace_binding,
)


def _binding(**overrides):
    values = {
        'runtime_ref': 'tmux:%41',
        'pane_state': 'alive',
        'active_pane_id': '%41',
        'pane_id': '%41',
        'tmux_socket_path': '/tmp/ccb.sock',
        'session_file': '',
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_declared_binding_tmux_socket_path_prefers_session_file_authority(tmp_path: Path) -> None:
    session_file = tmp_path / 'session.json'
    session_file.write_text('{"tmux_socket_path": "/tmp/from-session.sock"}', encoding='utf-8')

    declared, socket_path = declared_binding_tmux_socket_path(_binding(session_file=str(session_file), tmux_socket_path=''))

    assert declared is True
    assert socket_path == '/tmp/from-session.sock'


def test_usable_project_namespace_binding_requires_matching_namespace_record() -> None:
    binding = _binding()
    record = SimpleNamespace(matches=lambda **kwargs: kwargs['slot_key'] == 'agent1' and kwargs['project_id'] == 'proj-1')

    usable = usable_project_namespace_binding(
        binding,
        tmux_socket_path='/tmp/ccb.sock',
        tmux_session_name='ccb-demo',
        workspace_window_id='@2',
        agent_name='agent1',
        project_id='proj-1',
        tmux_backend_factory=lambda socket_path=None: SimpleNamespace(socket_path=socket_path),
        inspect_project_namespace_pane_fn=lambda backend, pane_id: record,
        same_tmux_socket_path_fn=lambda left, right: str(left or '') == str(right or ''),
    )

    assert usable is binding


def test_usable_agent_only_project_binding_accepts_undeclared_socket_binding() -> None:
    binding = _binding(session_file='', tmux_socket_path='', pane_state='unknown')

    usable = usable_agent_only_project_binding(
        binding,
        tmux_socket_path='/tmp/current.sock',
        tmux_session_name='ccb-demo',
        workspace_window_id='@2',
        agent_name='agent1',
        project_id='proj-1',
        tmux_backend_factory=lambda socket_path=None: SimpleNamespace(socket_path=socket_path),
        inspect_project_namespace_pane_fn=lambda backend, pane_id: None,
        same_tmux_socket_path_fn=lambda left, right: str(left or '') == str(right or ''),
    )

    assert usable is binding


def test_relabel_project_namespace_pane_applies_identity_for_project_socket() -> None:
    applied: list[tuple[str, str, dict[str, object]]] = []

    class Backend:
        def set_pane_title(self, pane_id: str, title: str) -> None:
            return None

        def set_pane_user_option(self, pane_id: str, key: str, value: str) -> None:
            return None

    pane_id = relabel_project_namespace_pane(
        binding=_binding(),
        agent_name='agent1',
        project_id='proj-1',
        style_index=2,
        tmux_socket_path='/tmp/ccb.sock',
        namespace_epoch=5,
        tmux_backend_factory=lambda socket_path=None: Backend(),
        same_tmux_socket_path_fn=lambda left, right: str(left or '') == str(right or ''),
        apply_ccb_pane_identity_fn=lambda backend, pane, **kwargs: applied.append((pane, kwargs['title'], kwargs)),
    )

    assert pane_id == '%41'
    assert applied == [
        (
            '%41',
            'agent1',
            {
                'title': 'agent1',
                'agent_label': 'agent1',
                'project_id': 'proj-1',
                'order_index': 2,
                'slot_key': 'agent1',
                'namespace_epoch': 5,
                'managed_by': 'ccbd',
            },
        )
    ]


def test_usable_project_namespace_binding_rejects_old_workspace_window() -> None:
    binding = _binding()
    record = SimpleNamespace(matches=lambda **kwargs: kwargs.get('window_id') == '@2')

    usable = usable_project_namespace_binding(
        binding,
        tmux_socket_path='/tmp/ccb.sock',
        tmux_session_name='ccb-demo',
        workspace_window_id='@3',
        agent_name='agent1',
        project_id='proj-1',
        tmux_backend_factory=lambda socket_path=None: SimpleNamespace(socket_path=socket_path),
        inspect_project_namespace_pane_fn=lambda backend, pane_id: record,
        same_tmux_socket_path_fn=lambda left, right: str(left or '') == str(right or ''),
    )

    assert usable is None


def test_usable_project_namespace_binding_rejects_provider_identity_mismatch() -> None:
    binding = _binding(
        provider='codex',
        provider_identity_state='mismatch',
        provider_identity_reason='live_codex_process_not_running_bound_resume_session',
    )
    record = SimpleNamespace(matches=lambda **kwargs: True)

    usable = usable_project_namespace_binding(
        binding,
        tmux_socket_path='/tmp/ccb.sock',
        tmux_session_name='ccb-demo',
        workspace_window_id='@2',
        agent_name='agent1',
        project_id='proj-1',
        tmux_backend_factory=lambda socket_path=None: SimpleNamespace(socket_path=socket_path),
        inspect_project_namespace_pane_fn=lambda backend, pane_id: record,
        same_tmux_socket_path_fn=lambda left, right: str(left or '') == str(right or ''),
    )

    assert usable is None


def test_usable_project_namespace_binding_rejects_unproven_provider_identity() -> None:
    binding = _binding(
        provider='codex',
        provider_identity_state='unknown',
        provider_identity_reason='pane_pid_unavailable',
    )
    record = SimpleNamespace(matches=lambda **kwargs: True)

    usable = usable_project_namespace_binding(
        binding,
        tmux_socket_path='/tmp/ccb.sock',
        tmux_session_name='ccb-demo',
        workspace_window_id='@2',
        agent_name='agent1',
        project_id='proj-1',
        tmux_backend_factory=lambda socket_path=None: SimpleNamespace(socket_path=socket_path),
        inspect_project_namespace_pane_fn=lambda backend, pane_id: record,
        same_tmux_socket_path_fn=lambda left, right: str(left or '') == str(right or ''),
    )

    assert usable is None
