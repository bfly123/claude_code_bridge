from __future__ import annotations

from dataclasses import replace
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
        _registry=SimpleNamespace(upsert=lambda updated: (_ for _ in ()).throw(AssertionError('fallback registry path should not be used'))),
        _runtime_service=SimpleNamespace(
            mutate_runtime_authority=lambda runtime, **updates: captured.setdefault('authority', replace(runtime, **updates)),
            patch_runtime_state=lambda runtime, **updates: captured.setdefault('runtime', replace(runtime, **updates)),
        ),
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
    assert captured['authority'].state is AgentState.DEGRADED
    assert captured['authority'].runtime_ref == 'tmux:%9'
    assert captured['authority'].session_ref == 'fact-session'
    assert updated.state is AgentState.IDLE
    assert updated.health == 'healthy'
    assert updated.pid == 33
    assert updated.session_ref == 'fact-session'
    assert updated.pane_id == '%9'
    assert updated.active_pane_id == '%9'
    assert updated.runtime_root == '/new/runtime'
    assert updated.session_file == '/tmp/session.json'
    assert updated.session_id == 'sid-9'
    assert updated.pane_state == 'alive'


def test_rebind_runtime_falls_back_to_session_binding_when_facts_missing(monkeypatch) -> None:
    runtime = _runtime(session_ref=None, health='restored')
    monitor = SimpleNamespace(
        _provider_runtime_facts=lambda runtime, session, binding, pane_id_override=None: None,
        _clock=lambda: '2026-04-06T00:00:00Z',
        _registry=SimpleNamespace(upsert=lambda updated: updated),
        _runtime_service=None,
    )
    binding = SimpleNamespace(session_id_attr='session_id', session_path_attr='session_path')
    monkeypatch.setattr(
        'ccbd.services.health_monitor_runtime.updates_runtime.rebind.session_ref',
        lambda session, session_id_attr, session_path_attr: 'bound-session',
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
    assert updated.pane_id == '%7'
    assert updated.active_pane_id == '%7'
    assert updated.pane_state == 'alive'
