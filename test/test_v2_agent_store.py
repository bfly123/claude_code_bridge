from __future__ import annotations

from pathlib import Path

from agents.models import (
    AgentRuntime,
    AgentState,
    AgentRestoreState,
    AgentSpec,
    PermissionMode,
    QueuePolicy,
    RestoreMode,
    RestoreStatus,
    RuntimeBindingSource,
    RuntimeMode,
    WorkspaceMode,
)
from agents.store import AgentRestoreStore, AgentRuntimeStore, AgentSpecStore
from storage.paths import PathLayout


def test_agent_stores_roundtrip(tmp_path: Path) -> None:
    layout = PathLayout(tmp_path / 'repo')
    spec = AgentSpec(
        name='agent1',
        provider='codex',
        target='.',
        workspace_mode=WorkspaceMode.GIT_WORKTREE,
        workspace_root=None,
        runtime_mode=RuntimeMode.PANE_BACKED,
        restore_default=RestoreMode.AUTO,
        permission_default=PermissionMode.MANUAL,
        queue_policy=QueuePolicy.SERIAL_PER_AGENT,
        branch_template='ccb/{agent_name}',
    )
    runtime = AgentRuntime(
        agent_name='agent1',
        state=AgentState.IDLE,
        pid=123,
        started_at='2026-03-18T00:00:00Z',
        last_seen_at='2026-03-18T00:00:01Z',
        runtime_ref='runtime-1',
        session_ref='session-1',
        workspace_path=str(layout.workspace_path('agent1')),
        project_id='proj-1',
        backend_type='tmux',
        queue_depth=0,
        socket_path=str(layout.ccbd_socket_path),
        health='healthy',
        binding_source=RuntimeBindingSource.EXTERNAL_ATTACH,
        daemon_generation=3,
        desired_state='mounted',
        reconcile_state='steady',
        restart_count=2,
        last_reconcile_at='2026-03-18T00:00:02Z',
        last_failure_reason='pane-dead',
    )
    restore = AgentRestoreState(
        restore_mode=RestoreMode.AUTO,
        last_checkpoint='checkpoint.md',
        conversation_summary='summary',
        open_tasks=['task1'],
        files_touched=['a.py'],
        base_commit='abc',
        head_commit='def',
        last_restore_status=RestoreStatus.PROVIDER,
    )

    AgentSpecStore(layout).save(spec)
    AgentRuntimeStore(layout).save(runtime)
    AgentRestoreStore(layout).save('agent1', restore)

    assert AgentSpecStore(layout).load('agent1') == spec
    assert AgentRuntimeStore(layout).load('agent1') == runtime
    loaded_restore = AgentRestoreStore(layout).load('agent1')
    assert loaded_restore is not None
    assert loaded_restore.last_restore_status is RestoreStatus.PROVIDER
    assert loaded_restore.files_touched == ['a.py']
