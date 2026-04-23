from __future__ import annotations

from types import SimpleNamespace

from agents.models import AgentRuntime, AgentState
from ccbd.services.health_monitor_runtime.updates_runtime.rebind import rebind_runtime
from ccbd.services.provider_runtime_facts import ProviderRuntimeFacts


def _runtime(**overrides) -> AgentRuntime:
    values = {
        'agent_name': 'agent1',
        'state': AgentState.IDLE,
        'pid': 11,
        'started_at': '2026-04-01T00:00:00Z',
        'last_seen_at': '2026-04-01T00:00:01Z',
        'runtime_ref': 'tmux:%1',
        'session_ref': 'runtime-session',
        'workspace_path': '/tmp/workspace',
        'project_id': 'proj-1',
        'backend_type': 'pane-backed',
        'queue_depth': 0,
        'socket_path': None,
        'health': 'healthy',
        'provider': 'codex',
        'runtime_root': '/tmp/runtime',
        'runtime_pid': 22,
        'job_id': 'job-object-old',
        'job_owner_pid': 44,
        'terminal_backend': 'tmux',
        'pane_id': '%1',
        'active_pane_id': '%1',
        'pane_title_marker': 'agent1',
        'pane_state': 'dead',
    }
    values.update(overrides)
    return AgentRuntime(**values)


def test_rebind_runtime_uses_provider_facts_and_clears_degraded_state() -> None:
    runtime = _runtime(state=AgentState.DEGRADED, health='restored')
    facts = ProviderRuntimeFacts(
        runtime_ref='tmux:%9',
        session_ref='fact-session',
        runtime_root='/new/runtime',
        runtime_pid=33,
        job_id='job-object-9',
        job_owner_pid=909,
        terminal_backend='tmux',
        pane_id='%9',
        pane_title_marker='agent1-new',
        pane_state='alive',
        tmux_socket_name='sock',
        tmux_socket_path='/tmp/tmux.sock',
        session_file='/tmp/session.json',
        session_id='sid-9',
    )
    captured = {}
    monitor = SimpleNamespace(
        _provider_runtime_facts=lambda runtime, session, binding, pane_id_override=None: facts,
        _clock=lambda: '2026-04-06T00:00:00Z',
        _registry=SimpleNamespace(upsert=lambda updated: captured.setdefault('runtime', updated)),
    )
    binding = SimpleNamespace(session_id_attr='session_id', session_path_attr='session_path')

    updated = rebind_runtime(
        monitor,
        runtime,
        session=SimpleNamespace(pane_id='%4'),
        binding=binding,
        pane_id_override='%8',
        force_session_ref_update=True,
    )

    assert updated is captured['runtime']
    assert updated.state is AgentState.IDLE
    assert updated.health == 'healthy'
    assert updated.pid == 33
    assert updated.session_ref == 'fact-session'
    assert updated.pane_id == '%9'
    assert updated.active_pane_id == '%9'
    assert updated.runtime_root == '/new/runtime'
    assert updated.session_file == '/tmp/session.json'
    assert updated.session_id == 'sid-9'
    assert updated.job_id == 'job-object-9'
    assert updated.job_owner_pid == 909
    assert updated.pane_state == 'alive'


def test_rebind_runtime_falls_back_to_session_binding_when_facts_missing(monkeypatch) -> None:
    runtime = _runtime(session_ref=None, health='restored')
    monitor = SimpleNamespace(
        _provider_runtime_facts=lambda runtime, session, binding, pane_id_override=None: None,
        _clock=lambda: '2026-04-06T00:00:00Z',
        _registry=SimpleNamespace(upsert=lambda updated: updated),
    )
    binding = SimpleNamespace(session_id_attr='session_id', session_path_attr='session_path')
    monkeypatch.setattr(
        'ccbd.services.health_monitor_runtime.updates_runtime.rebind.session_ref',
        lambda session, session_id_attr, session_path_attr: 'bound-session',
    )
    monkeypatch.setattr(
        'ccbd.services.health_monitor_runtime.updates_runtime.common.session_runtime_ref',
        lambda session: 'tmux:%7',
    )
    monkeypatch.setattr(
        'ccbd.services.health_monitor_runtime.updates_runtime.common.session_runtime_root',
        lambda session: '/session/runtime',
    )
    monkeypatch.setattr(
        'ccbd.services.health_monitor_runtime.updates_runtime.common.session_runtime_pid',
        lambda session, provider: 707,
    )
    monkeypatch.setattr(
        'ccbd.services.health_monitor_runtime.updates_runtime.common.session_terminal',
        lambda session: 'psmux',
    )
    monkeypatch.setattr(
        'ccbd.services.health_monitor_runtime.updates_runtime.common.session_pane_title_marker',
        lambda session: 'agent1-session',
    )
    monkeypatch.setattr(
        'ccbd.services.health_monitor_runtime.updates_runtime.common.session_tmux_socket_name',
        lambda session: 'sock-session',
    )
    monkeypatch.setattr(
        'ccbd.services.health_monitor_runtime.updates_runtime.common.session_tmux_socket_path',
        lambda session: r'\\.\pipe\psmux-session',
    )
    monkeypatch.setattr(
        'ccbd.services.health_monitor_runtime.updates_runtime.common.session_file',
        lambda session: '/tmp/session.json',
    )
    monkeypatch.setattr(
        'ccbd.services.health_monitor_runtime.updates_runtime.common.session_id',
        lambda session, session_id_attr: 'sid-session',
    )
    monkeypatch.setattr(
        'ccbd.services.health_monitor_runtime.updates_runtime.common.session_job_id',
        lambda session: 'job-object-session',
    )
    monkeypatch.setattr(
        'ccbd.services.health_monitor_runtime.updates_runtime.common.session_job_owner_pid',
        lambda session: 808,
    )

    updated = rebind_runtime(
        monitor,
        runtime,
        session=SimpleNamespace(pane_id=''),
        binding=binding,
        pane_id_override='%7',
    )

    assert updated.state is AgentState.IDLE
    assert updated.health == 'restored'
    assert updated.session_ref == 'bound-session'
    assert updated.runtime_ref == 'tmux:%7'
    assert updated.pane_id == '%7'
    assert updated.active_pane_id == '%7'
    assert updated.runtime_root == '/session/runtime'
    assert updated.runtime_pid == 707
    assert updated.terminal_backend == 'psmux'
    assert updated.pane_title_marker == 'agent1-session'
    assert updated.tmux_socket_name == 'sock-session'
    assert updated.tmux_socket_path == r'\\.\pipe\psmux-session'
    assert updated.session_file == '/tmp/session.json'
    assert updated.session_id == 'sid-session'
    assert updated.job_id == 'job-object-session'
    assert updated.job_owner_pid == 808
    assert updated.pane_state == 'alive'
