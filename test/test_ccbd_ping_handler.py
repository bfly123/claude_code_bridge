from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from agents.models import (
    AgentRuntime,
    AgentSpec,
    AgentState,
    PermissionMode,
    ProjectConfig,
    QueuePolicy,
    RestoreMode,
    RuntimeMode,
    WorkspaceMode,
)
from ccbd.handlers.ping_runtime.handler import build_ping_handler
from ccbd.models import CcbdLease, LeaseHealth, LeaseInspection, MountState
from storage.paths import PathLayout


def _provider_config(*providers: str) -> ProjectConfig:
    agents: dict[str, AgentSpec] = {}
    for provider in providers:
        agents[provider] = AgentSpec(
            name=provider,
            provider=provider,
            target='.',
            workspace_mode=WorkspaceMode.GIT_WORKTREE,
            workspace_root=None,
            runtime_mode=RuntimeMode.PANE_BACKED,
            restore_default=RestoreMode.AUTO,
            permission_default=PermissionMode.MANUAL,
            queue_policy=QueuePolicy.SERIAL_PER_AGENT,
        )
    return ProjectConfig(version=2, default_agents=tuple(providers), agents=agents)


def _inspection(project_id: str, socket_path: str) -> LeaseInspection:
    lease = CcbdLease(
        project_id=project_id,
        ccbd_pid=123,
        socket_path=socket_path,
        ipc_kind='named_pipe',
        owner_uid=1000,
        boot_id='boot-1',
        started_at='2026-04-21T00:00:00Z',
        last_heartbeat_at='2026-04-21T00:00:00Z',
        mount_state=MountState.MOUNTED,
        generation=7,
        backend_family='tmux',
        backend_impl='psmux',
    )
    return LeaseInspection(
        lease=lease,
        health=LeaseHealth.HEALTHY,
        pid_alive=True,
        socket_connectable=True,
        heartbeat_fresh=True,
        takeover_allowed=False,
        reason='healthy',
    )


def _runtime(agent_name: str, *, project_id: str, layout: PathLayout, pid: int) -> AgentRuntime:
    return AgentRuntime(
        agent_name=agent_name,
        state=AgentState.IDLE,
        pid=pid,
        started_at='2026-04-21T00:00:00Z',
        last_seen_at='2026-04-21T00:00:00Z',
        runtime_ref=f'tmux:%{pid}',
        session_ref=f'{agent_name}-session',
        workspace_path=str(layout.workspace_path(agent_name)),
        project_id=project_id,
        backend_type='pane-backed',
        queue_depth=0,
        socket_path=None,
        health='healthy',
        provider=agent_name,
    )


def test_ping_handler_ccbd_skips_runtime_health_scan(tmp_path: Path) -> None:
    layout = PathLayout(tmp_path / 'repo-ping-ccbd')
    project_id = 'proj-ccbd'
    inspection = _inspection(project_id, str(layout.ccbd_socket_path))
    calls: list[str] = []

    handler = build_ping_handler(
        project_id=project_id,
        config=_provider_config('codex'),
        registry=SimpleNamespace(),
        health_monitor=SimpleNamespace(
            check_all=lambda: calls.append('check_all'),
            daemon_health=lambda: calls.append('daemon_health') or inspection,
            _runtime_health=lambda runtime: calls.append(f'runtime:{runtime.agent_name}'),
        ),
        execution_registry=SimpleNamespace(get=lambda provider: None),
    )

    payload = handler({'target': 'ccbd'})

    assert payload['health'] == 'healthy'
    assert calls == ['daemon_health']


def test_ping_handler_agent_target_refreshes_only_requested_runtime(tmp_path: Path) -> None:
    layout = PathLayout(tmp_path / 'repo-ping-agent')
    project_id = 'proj-agent'
    inspection = _inspection(project_id, str(layout.ccbd_socket_path))
    codex = _runtime('codex', project_id=project_id, layout=layout, pid=101)
    claude = _runtime('claude', project_id=project_id, layout=layout, pid=202)
    runtimes = {'codex': codex, 'claude': replace(claude, health='pane-dead')}
    calls: list[str] = []

    registry = SimpleNamespace(
        get=lambda agent_name: runtimes.get(agent_name),
        spec_for=lambda agent_name: _provider_config('codex', 'claude').agents[agent_name],
    )
    handler = build_ping_handler(
        project_id=project_id,
        config=_provider_config('codex', 'claude'),
        registry=registry,
        health_monitor=SimpleNamespace(
            check_all=lambda: calls.append('check_all'),
            daemon_health=lambda: calls.append('daemon_health') or inspection,
            _runtime_health=lambda runtime: calls.append(f'runtime:{runtime.agent_name}') or runtime.health,
        ),
        execution_registry=SimpleNamespace(get=lambda provider: None),
    )

    payload = handler({'target': 'codex'})

    assert payload['agent_name'] == 'codex'
    assert payload['health'] == 'healthy'
    assert calls == ['runtime:codex', 'daemon_health']


def test_ping_handler_all_keeps_full_health_scan(tmp_path: Path) -> None:
    layout = PathLayout(tmp_path / 'repo-ping-all')
    project_id = 'proj-all'
    inspection = _inspection(project_id, str(layout.ccbd_socket_path))
    calls: list[str] = []
    config = _provider_config('codex', 'claude')
    registry = SimpleNamespace(
        list_known_agents=lambda: ('codex', 'claude'),
        spec_for=lambda agent_name: config.agents[agent_name],
        get=lambda agent_name: _runtime(agent_name, project_id=project_id, layout=layout, pid=100 if agent_name == 'codex' else 200),
    )
    handler = build_ping_handler(
        project_id=project_id,
        config=config,
        registry=registry,
        health_monitor=SimpleNamespace(
            check_all=lambda: calls.append('check_all'),
            daemon_health=lambda: calls.append('daemon_health') or inspection,
            _runtime_health=lambda runtime: calls.append(f'runtime:{runtime.agent_name}'),
        ),
        execution_registry=SimpleNamespace(get=lambda provider: None),
    )

    payload = handler({'target': 'all'})

    assert payload['project_id'] == project_id
    assert [agent['agent_name'] for agent in payload['agents']] == ['codex', 'claude']
    assert calls == ['check_all', 'daemon_health']
