from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

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
from ccbd.services.registry import AgentRegistry
from provider_runtime.helper_manifest import build_runtime_helper_manifest
from provider_runtime.helper_manifest import load_helper_manifest
from storage.paths import PathLayout


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


def test_registry_remove_clears_helper_manifest(tmp_path: Path) -> None:
    layout = PathLayout(tmp_path / 'repo')
    registry = AgentRegistry(layout, _config())
    helper_path = layout.agent_helper_path('demo')
    helper_path.parent.mkdir(parents=True, exist_ok=True)
    helper_path.write_text(
        (
            '{"schema_version":1,"record_type":"provider_helper_manifest","agent_name":"demo",'
            '"runtime_generation":2,"helper_kind":"codex_bridge","leader_pid":111,"pgid":111,'
            '"started_at":"2026-04-22T00:00:00Z","owner_daemon_generation":5,"state":"running"}\n'
        ),
        encoding='utf-8',
    )
    registry.upsert(
        AgentRuntime(
            agent_name='demo',
            state=AgentState.IDLE,
            pid=123,
            started_at='2026-04-22T00:00:00Z',
            last_seen_at='2026-04-22T00:00:01Z',
            runtime_ref='tmux:%1',
            session_ref='session-1',
            workspace_path=str(layout.workspace_path('demo')),
            project_id='proj-1',
            backend_type='pane-backed',
            queue_depth=1,
            socket_path=None,
            health='healthy',
            provider='codex',
            runtime_root=str(layout.agent_provider_runtime_dir('demo', 'codex')),
        )
    )

    removed = registry.remove('demo')

    assert removed is not None
    assert removed.state is AgentState.STOPPED
    assert helper_path.exists() is False


def test_registry_remove_clears_helper_manifest_without_runtime(tmp_path: Path) -> None:
    layout = PathLayout(tmp_path / 'repo')
    registry = AgentRegistry(layout, _config())
    helper_path = layout.agent_helper_path('demo')
    helper_path.parent.mkdir(parents=True, exist_ok=True)
    helper_path.write_text(
        (
            '{"schema_version":1,"record_type":"provider_helper_manifest","agent_name":"demo",'
            '"runtime_generation":2,"helper_kind":"codex_bridge","leader_pid":111,"pgid":111,'
            '"started_at":"2026-04-22T00:00:00Z","owner_daemon_generation":5,"state":"running"}\n'
        ),
        encoding='utf-8',
    )

    removed = registry.remove('demo')

    assert removed is None
    assert helper_path.exists() is False


def test_registry_upsert_syncs_helper_manifest_with_final_runtime_authority(tmp_path: Path) -> None:
    layout = PathLayout(tmp_path / 'repo')
    registry = AgentRegistry(layout, _config())
    runtime_root = layout.agent_provider_runtime_dir('demo', 'codex')
    runtime_root.mkdir(parents=True, exist_ok=True)
    (runtime_root / 'bridge.pid').write_text('5511\n', encoding='utf-8')

    saved = registry.upsert(
        AgentRuntime(
            agent_name='demo',
            state=AgentState.IDLE,
            pid=123,
            started_at='2026-04-22T00:00:00Z',
            last_seen_at='2026-04-22T00:00:01Z',
            runtime_ref='tmux:%1',
            session_ref='session-1',
            workspace_path=str(layout.workspace_path('demo')),
            project_id='proj-1',
            backend_type='pane-backed',
            queue_depth=1,
            socket_path=None,
            health='healthy',
            provider='codex',
            runtime_root=str(runtime_root),
            runtime_generation=4,
            daemon_generation=7,
        )
    )

    manifest = load_helper_manifest(layout.agent_helper_path('demo'))

    assert manifest is not None
    assert manifest.leader_pid == 5511
    assert manifest.runtime_generation == 4
    assert manifest.owner_daemon_generation == 7
    assert manifest.started_at == saved.started_at


def test_registry_upsert_rejects_authority_mutation_without_authority_write(tmp_path: Path) -> None:
    layout = PathLayout(tmp_path / 'repo')
    registry = AgentRegistry(layout, _config())
    saved = registry.upsert(
        AgentRuntime(
            agent_name='demo',
            state=AgentState.IDLE,
            pid=123,
            started_at='2026-04-22T00:00:00Z',
            last_seen_at='2026-04-22T00:00:01Z',
            runtime_ref='tmux:%1',
            session_ref='session-1',
            workspace_path=str(layout.workspace_path('demo')),
            project_id='proj-1',
            backend_type='pane-backed',
            queue_depth=1,
            socket_path=None,
            health='healthy',
            provider='codex',
            runtime_root=str(layout.agent_provider_runtime_dir('demo', 'codex')),
            runtime_generation=4,
            daemon_generation=7,
        )
    )

    with pytest.raises(ValueError, match='authority write required'):
        registry.upsert(
            replace(
                saved,
                runtime_generation=5,
                daemon_generation=8,
            )
        )


def test_registry_upsert_allows_state_only_mutation_without_authority_write(tmp_path: Path) -> None:
    layout = PathLayout(tmp_path / 'repo')
    registry = AgentRegistry(layout, _config())
    saved = registry.upsert(
        AgentRuntime(
            agent_name='demo',
            state=AgentState.IDLE,
            pid=123,
            started_at='2026-04-22T00:00:00Z',
            last_seen_at='2026-04-22T00:00:01Z',
            runtime_ref='tmux:%1',
            session_ref='session-1',
            workspace_path=str(layout.workspace_path('demo')),
            project_id='proj-1',
            backend_type='pane-backed',
            queue_depth=1,
            socket_path=None,
            health='healthy',
            provider='codex',
            runtime_root=str(layout.agent_provider_runtime_dir('demo', 'codex')),
            runtime_generation=4,
            daemon_generation=7,
        )
    )

    updated = registry.upsert(
        replace(
            saved,
            state=AgentState.BUSY,
            queue_depth=2,
            health='healthy',
            last_seen_at='2026-04-22T00:00:02Z',
        )
    )

    assert updated.state is AgentState.BUSY
    assert updated.queue_depth == 2
    assert updated.runtime_generation == 4
    assert updated.daemon_generation == 7


def test_build_runtime_helper_manifest_requires_canonical_runtime_generation(tmp_path: Path) -> None:
    layout = PathLayout(tmp_path / 'repo')
    runtime_root = layout.agent_provider_runtime_dir('demo', 'codex')
    runtime_root.mkdir(parents=True, exist_ok=True)
    (runtime_root / 'bridge.pid').write_text('5511\n', encoding='utf-8')

    manifest = build_runtime_helper_manifest(
        AgentRuntime(
            agent_name='demo',
            state=AgentState.IDLE,
            pid=123,
            started_at='2026-04-22T00:00:00Z',
            last_seen_at='2026-04-22T00:00:01Z',
            runtime_ref='tmux:%1',
            session_ref='session-1',
            workspace_path=str(layout.workspace_path('demo')),
            project_id='proj-1',
            backend_type='pane-backed',
            queue_depth=1,
            socket_path=None,
            health='healthy',
            provider='codex',
            runtime_root=str(runtime_root),
            binding_generation=9,
            runtime_generation=None,
        )
    )

    assert manifest is None
