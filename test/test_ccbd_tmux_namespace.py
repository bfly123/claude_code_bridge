from __future__ import annotations

from types import SimpleNamespace

from ccbd.services.health_assessment.tmux_runtime.namespace import pane_outside_project_namespace


def test_pane_outside_namespace_accepts_runtime_socket_fallback(monkeypatch) -> None:
    runtime = SimpleNamespace(project_id='proj-1', agent_name='agent1', tmux_socket_path='/tmp/ccb.sock')
    namespace_store = SimpleNamespace(
        load=lambda: SimpleNamespace(tmux_socket_path='/tmp/ccb.sock', tmux_session_name='sess-1')
    )

    monkeypatch.setattr(
        'ccbd.services.health_assessment.tmux_runtime.namespace.backend_socket_matches',
        lambda backend, tmux_socket_path: False,
    )
    monkeypatch.setattr(
        'ccbd.services.health_assessment.tmux_runtime.namespace.same_tmux_socket_path',
        lambda left, right: left == right,
    )

    assert pane_outside_project_namespace(
        runtime=runtime,
        namespace_state_store=namespace_store,
        backend=object(),
        pane_id='%3',
    ) is True


def test_pane_outside_namespace_checks_project_namespace_record(monkeypatch) -> None:
    runtime = SimpleNamespace(project_id='proj-1', agent_name='agent1', tmux_socket_path='/tmp/ccb.sock')
    namespace_store = SimpleNamespace(
        load=lambda: SimpleNamespace(tmux_socket_path='/tmp/ccb.sock', tmux_session_name='sess-1')
    )
    record = SimpleNamespace(
        matches=lambda **kwargs: kwargs == {
            'tmux_session_name': 'sess-1',
            'project_id': 'proj-1',
            'role': 'agent',
            'slot_key': 'agent1',
            'managed_by': 'ccbd',
        }
    )

    monkeypatch.setattr(
        'ccbd.services.health_assessment.tmux_runtime.namespace.backend_socket_matches',
        lambda backend, tmux_socket_path: True,
    )
    monkeypatch.setattr(
        'ccbd.services.health_assessment.tmux_runtime.namespace.inspect_project_namespace_pane',
        lambda backend, pane_id: record,
    )

    assert pane_outside_project_namespace(
        runtime=runtime,
        namespace_state_store=namespace_store,
        backend=object(),
        pane_id='%3',
    ) is False


def test_pane_outside_namespace_rejects_old_workspace_window(monkeypatch) -> None:
    runtime = SimpleNamespace(
        project_id='proj-1',
        agent_name='agent1',
        slot_key='agent1',
        tmux_socket_path='/tmp/ccb.sock',
    )
    namespace_store = SimpleNamespace(
        load=lambda: SimpleNamespace(
            tmux_socket_path='/tmp/ccb.sock',
            tmux_session_name='sess-1',
            workspace_window_id='@2',
        )
    )
    record = SimpleNamespace(
        window_id='@1',
        matches=lambda **kwargs: True,
    )

    monkeypatch.setattr(
        'ccbd.services.health_assessment.tmux_runtime.namespace.backend_socket_matches',
        lambda backend, tmux_socket_path: True,
    )
    monkeypatch.setattr(
        'ccbd.services.health_assessment.tmux_runtime.namespace.inspect_project_namespace_pane',
        lambda backend, pane_id: record,
    )

    assert pane_outside_project_namespace(
        runtime=runtime,
        namespace_state_store=namespace_store,
        backend=object(),
        pane_id='%3',
    ) is True
