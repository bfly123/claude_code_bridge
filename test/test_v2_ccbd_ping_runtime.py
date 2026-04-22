from __future__ import annotations

from types import SimpleNamespace

from agents.models import (
    AgentRuntime,
    AgentState,
    AgentSpec,
    PermissionMode,
    ProjectConfig,
    QueuePolicy,
    RestoreMode,
    RuntimeMode,
    WorkspaceMode,
)
from ccbd.handlers.ping_runtime.handler import build_ping_handler
from ccbd.handlers.ping_runtime.payloads import build_ccbd_payload
from ccbd.models import LeaseHealth


def _config() -> ProjectConfig:
    spec = AgentSpec(
        name='demo',
        provider='codex',
        target='.',
        workspace_mode=WorkspaceMode.GIT_WORKTREE,
        workspace_root=None,
        runtime_mode=RuntimeMode.PANE_BACKED,
        restore_default=RestoreMode.AUTO,
        permission_default=PermissionMode.MANUAL,
        queue_policy=QueuePolicy.SERIAL_PER_AGENT,
    )
    return ProjectConfig(version=2, default_agents=('demo',), agents={'demo': spec})


def _inspection(*, phase: str, desired_state: str, socket_path: str = '/tmp/ccbd.sock'):
    return SimpleNamespace(
        phase=phase,
        desired_state=desired_state,
        health=LeaseHealth.UNMOUNTED,
        generation=7,
        socket_path=socket_path,
        pid_alive=False,
        socket_connectable=False,
        heartbeat_fresh=False,
        takeover_allowed=True,
        reason='lease_unmounted',
        last_failure_reason='startup_in_progress' if phase == 'starting' else None,
        shutdown_intent=None,
        lease=SimpleNamespace(
            mount_state=SimpleNamespace(value='unmounted'),
            socket_path=socket_path,
            last_heartbeat_at='2026-04-21T00:00:00Z',
        ),
    )


def test_build_ccbd_payload_prefers_lifecycle_phase_over_lease_mount_state() -> None:
    payload = build_ccbd_payload(
        project_id='proj-1',
        config=_config(),
        inspection=_inspection(phase='starting', desired_state='running'),
        execution_summary={},
        restore_summary={},
        namespace_summary={},
        namespace_event_summary={},
        start_policy_summary={},
    )

    assert payload['mount_state'] == 'starting'
    assert payload['desired_state'] == 'running'
    assert payload['socket_path'] == '/tmp/ccbd.sock'
    assert payload['diagnostics']['last_failure_reason'] == 'startup_in_progress'


def test_ping_handler_all_uses_lifecycle_phase_for_ccbd_state() -> None:
    config = _config()
    handler = build_ping_handler(
        project_id='proj-1',
        config=config,
        registry=SimpleNamespace(
            list_known_agents=lambda: ('demo',),
            spec_for=lambda name: config.agents[name],
            get=lambda name: None,
        ),
        health_monitor=SimpleNamespace(
            check_all=lambda: {},
            daemon_health=lambda: _inspection(phase='starting', desired_state='running'),
        ),
        execution_registry=SimpleNamespace(get=lambda provider: None),
        execution_state_store=SimpleNamespace(summary=lambda: {}),
    )

    payload = handler({'target': 'all'})

    assert payload['ccbd_state'] == 'starting'
    assert payload['agents'][0]['mount_state'] == 'starting'
    assert payload['agents'][0]['diagnostics']['desired_state'] == 'running'


def test_build_agent_payload_prefers_runtime_mount_state_over_project_phase() -> None:
    config = _config()
    runtime = AgentRuntime(
        agent_name='demo',
        state=AgentState.BUSY,
        pid=123,
        started_at='2026-04-22T00:00:00Z',
        last_seen_at='2026-04-22T00:00:01Z',
        runtime_ref='tmux:%1',
        session_ref='session-1',
        workspace_path='/tmp/ws',
        project_id='proj-1',
        backend_type='pane-backed',
        queue_depth=1,
        socket_path=None,
        health='healthy',
        provider='codex',
    )

    handler = build_ping_handler(
        project_id='proj-1',
        config=config,
        registry=SimpleNamespace(
            list_known_agents=lambda: ('demo',),
            spec_for=lambda name: config.agents[name],
            get=lambda name: runtime,
        ),
        health_monitor=SimpleNamespace(
            check_all=lambda: {},
            daemon_health=lambda: _inspection(phase='failed', desired_state='running'),
        ),
        execution_registry=SimpleNamespace(get=lambda provider: None),
        execution_state_store=SimpleNamespace(summary=lambda: {}),
    )

    payload = handler({'target': 'demo'})

    assert payload['mount_state'] == 'mounted'
    assert payload['runtime_state'] == 'busy'
    assert payload['health'] == 'healthy'
