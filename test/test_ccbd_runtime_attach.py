from __future__ import annotations

from types import SimpleNamespace

import pytest

from agents.models import AgentRuntime, AgentState, RuntimeBindingSource
from ccbd.services.runtime import RuntimeService
from ccbd.services.runtime_attach import resolve_session_fields
from ccbd.services.runtime_runtime.attach import attach_runtime


class _Registry:
    def __init__(self, existing: AgentRuntime | None = None, provider: str = 'codex') -> None:
        self._existing = existing
        self._spec = SimpleNamespace(name='agent1', provider=provider)
        self.last_upsert = None

    def spec_for(self, agent_name: str):
        assert agent_name == 'agent1'
        return self._spec

    def get(self, agent_name: str):
        assert agent_name == 'agent1'
        return self._existing

    def upsert(self, runtime):
        self.last_upsert = runtime
        return runtime


def _runtime(**overrides) -> AgentRuntime:
    values = {
        'agent_name': 'agent1',
        'state': AgentState.IDLE,
        'pid': 11,
        'started_at': '2026-04-01T00:00:00Z',
        'last_seen_at': '2026-04-01T00:00:01Z',
        'runtime_ref': 'tmux:%1',
        'session_ref': 'session-1',
        'workspace_path': '/tmp/ws',
        'project_id': 'proj-1',
        'backend_type': 'pane-backed',
        'queue_depth': 3,
        'socket_path': '/tmp/agent.sock',
        'health': 'healthy',
        'provider': 'codex',
        'runtime_root': '/tmp/runtime',
        'runtime_pid': 22,
        'terminal_backend': 'tmux',
        'pane_id': '%1',
        'active_pane_id': '%1',
        'pane_title_marker': 'agent1',
        'pane_state': 'alive',
        'binding_generation': 2,
        'daemon_generation': 2,
        'runtime_generation': 2,
        'managed_by': 'ccbd',
        'binding_source': RuntimeBindingSource.PROVIDER_SESSION,
    }
    values.update(overrides)
    return AgentRuntime(**values)


def test_resolve_session_fields_clears_implicit_fields_when_session_ref_is_explicitly_cleared() -> None:
    existing = _runtime(
        session_ref='session-1',
        session_file='/tmp/session.json',
        session_id='session-1',
    )

    session_file, session_id, session_ref = resolve_session_fields(
        existing,
        session_ref=None,
        session_file=None,
        session_id=None,
        session_ref_explicit=True,
        session_file_explicit=False,
        session_id_explicit=False,
    )

    assert session_file is None
    assert session_id is None
    assert session_ref is None


def test_attach_runtime_updates_active_existing_runtime() -> None:
    existing = _runtime()
    registry = _Registry(existing=existing)

    updated = attach_runtime(
        registry=registry,
        project_id='proj-new',
        clock=lambda: '2026-04-06T00:00:00Z',
        agent_name='agent1',
        workspace_path='/tmp/ws-next',
        backend_type='pane-backed',
        runtime_ref='tmux:%9',
        session_ref='session-9',
        health='healthy',
        runtime_pid=99,
        pane_title_marker='agent1-next',
    )

    assert updated is registry.last_upsert
    assert updated.started_at == '2026-04-06T00:00:00Z'
    assert updated.last_seen_at == '2026-04-06T00:00:00Z'
    assert updated.runtime_ref == 'tmux:%9'
    assert updated.terminal_backend == 'tmux'
    assert updated.pane_id == '%9'
    assert updated.active_pane_id == '%9'
    assert updated.session_ref == 'session-9'
    assert updated.runtime_pid == 99
    assert updated.pid == 99
    assert updated.binding_generation == 3
    assert updated.runtime_generation == 3
    assert updated.queue_depth == 3
    assert updated.socket_path == '/tmp/agent.sock'
    assert updated.project_id == 'proj-1'
    assert updated.slot_key == 'agent1'


def test_attach_runtime_creates_new_runtime_with_runtime_ref_derived_fields() -> None:
    registry = _Registry(existing=None)

    created = attach_runtime(
        registry=registry,
        project_id='proj-1',
        clock=lambda: '2026-04-06T00:00:00Z',
        agent_name='agent1',
        workspace_path='/tmp/ws',
        backend_type='pane-backed',
        runtime_ref='tmux:%4',
        session_ref='session-4',
    )

    assert created is registry.last_upsert
    assert created.started_at == '2026-04-06T00:00:00Z'
    assert created.last_seen_at == '2026-04-06T00:00:00Z'
    assert created.project_id == 'proj-1'
    assert created.runtime_ref == 'tmux:%4'
    assert created.terminal_backend == 'tmux'
    assert created.pane_id == '%4'
    assert created.active_pane_id == '%4'
    assert created.session_ref == 'session-4'
    assert created.binding_generation == 1
    assert created.runtime_generation == 1
    assert created.binding_source is RuntimeBindingSource.PROVIDER_SESSION
    assert created.slot_key == 'agent1'


def test_attach_runtime_preserves_runtime_generation_when_identity_is_unchanged() -> None:
    existing = _runtime(binding_generation=4, runtime_generation=4)
    registry = _Registry(existing=existing)

    updated = attach_runtime(
        registry=registry,
        project_id='proj-1',
        clock=lambda: '2026-04-06T00:00:00Z',
        agent_name='agent1',
        workspace_path='/tmp/ws',
        backend_type='pane-backed',
        runtime_ref='tmux:%1',
        session_ref='session-1',
        runtime_pid=22,
        pane_id='%1',
        active_pane_id='%1',
    )

    assert updated.started_at == existing.started_at
    assert updated.binding_generation == 4
    assert updated.runtime_generation == 4


def test_attach_runtime_rolls_authority_epoch_when_daemon_generation_changes() -> None:
    existing = _runtime(binding_generation=4, runtime_generation=4, daemon_generation=2)
    registry = _Registry(existing=existing)

    updated = attach_runtime(
        registry=registry,
        project_id='proj-1',
        clock=lambda: '2026-04-06T00:00:00Z',
        agent_name='agent1',
        workspace_path='/tmp/ws',
        backend_type='pane-backed',
        runtime_ref='tmux:%1',
        session_ref='session-1',
        runtime_pid=22,
        pane_id='%1',
        active_pane_id='%1',
        daemon_generation=3,
    )

    assert updated.started_at == '2026-04-06T00:00:00Z'
    assert updated.binding_generation == 5
    assert updated.runtime_generation == 5
    assert updated.daemon_generation == 3


def test_attach_runtime_uses_canonical_epoch_when_existing_generations_diverged() -> None:
    existing = _runtime(binding_generation=5, runtime_generation=4, daemon_generation=2)
    registry = _Registry(existing=existing)

    updated = attach_runtime(
        registry=registry,
        project_id='proj-1',
        clock=lambda: '2026-04-06T00:00:00Z',
        agent_name='agent1',
        workspace_path='/tmp/ws',
        backend_type='pane-backed',
        runtime_ref='tmux:%1',
        session_ref='session-1',
        runtime_pid=22,
        pane_id='%1',
        active_pane_id='%1',
        daemon_generation=3,
    )

    assert updated.started_at == '2026-04-06T00:00:00Z'
    assert updated.binding_generation == 6
    assert updated.runtime_generation == 6
    assert updated.daemon_generation == 3


def test_external_attach_promotes_failed_runtime_back_to_healthy() -> None:
    existing = _runtime(
        state=AgentState.FAILED,
        health='start-failed',
        binding_source=RuntimeBindingSource.PROVIDER_SESSION,
    )
    registry = _Registry(existing=existing)

    updated = attach_runtime(
        registry=registry,
        project_id='proj-1',
        clock=lambda: '2026-04-06T00:00:00Z',
        agent_name='agent1',
        workspace_path='/tmp/ws',
        backend_type='pane-backed',
        runtime_ref='tmux:%8',
        session_ref='session-8',
        binding_source=RuntimeBindingSource.EXTERNAL_ATTACH,
    )

    assert updated.health == 'healthy'
    assert updated.state is AgentState.IDLE
    assert updated.binding_source is RuntimeBindingSource.EXTERNAL_ATTACH


def test_external_attach_preserves_restored_health() -> None:
    existing = _runtime(
        state=AgentState.DEGRADED,
        health='restored',
        binding_source=RuntimeBindingSource.EXTERNAL_ATTACH,
    )
    registry = _Registry(existing=existing)

    updated = attach_runtime(
        registry=registry,
        project_id='proj-1',
        clock=lambda: '2026-04-06T00:00:00Z',
        agent_name='agent1',
        workspace_path='/tmp/ws',
        backend_type='pane-backed',
        runtime_ref='tmux:%8',
        session_ref='session-8',
        binding_source=RuntimeBindingSource.EXTERNAL_ATTACH,
    )

    assert updated.health == 'restored'
    assert updated.state is AgentState.IDLE
    assert updated.binding_source is RuntimeBindingSource.EXTERNAL_ATTACH


def test_patch_runtime_state_updates_allowed_fields_without_touching_authority() -> None:
    existing = _runtime(binding_generation=4, runtime_generation=4, daemon_generation=3)
    registry = _Registry(existing=existing)
    service = RuntimeService(SimpleNamespace(), registry, 'proj-1', clock=lambda: '2026-04-06T00:00:00Z')

    updated = service.patch_runtime_state(
        existing,
        state=AgentState.BUSY,
        queue_depth=7,
        last_seen_at='2026-04-06T00:00:00Z',
    )

    assert updated is registry.last_upsert
    assert updated.state is AgentState.BUSY
    assert updated.queue_depth == 7
    assert updated.binding_generation == 4
    assert updated.runtime_generation == 4
    assert updated.daemon_generation == 3
    assert updated.started_at == existing.started_at


def test_patch_runtime_state_rejects_authority_fields() -> None:
    existing = _runtime(binding_generation=4, runtime_generation=4, daemon_generation=3)
    registry = _Registry(existing=existing)
    service = RuntimeService(SimpleNamespace(), registry, 'proj-1', clock=lambda: '2026-04-06T00:00:00Z')

    with pytest.raises(ValueError, match='invalid runtime state patch fields: runtime_generation'):
        service.patch_runtime_state(existing, runtime_generation=9)
