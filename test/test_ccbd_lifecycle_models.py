from __future__ import annotations

from types import SimpleNamespace

from ccbd.models import CcbdRuntimeSnapshot, CcbdStartupAgentResult
from ccbd.models_runtime.lifecycle_runtime.shutdown import runtime_snapshots_summary


def test_startup_agent_result_roundtrip_preserves_windows_binding_metadata() -> None:
    result = CcbdStartupAgentResult(
        agent_name='agent1',
        provider='codex',
        action='attached',
        health='healthy',
        workspace_path='/tmp/ws',
        runtime_ref='psmux:%9',
        session_ref='session-1',
        session_file=r'C:\tmp\agent1.session.json',
        session_id='session-1',
        terminal_backend='psmux',
        tmux_socket_name='psmux-agent1',
        tmux_socket_path=r'\\.\pipe\psmux-agent1',
        pane_id='%9',
        active_pane_id='%9',
        pane_state='alive',
        runtime_pid=4321,
        runtime_root=r'C:\tmp\runtime',
        job_id='job-object-1',
        job_owner_pid=654,
    )

    restored = CcbdStartupAgentResult.from_record(result.to_record())

    assert restored.session_file == r'C:\tmp\agent1.session.json'
    assert restored.session_id == 'session-1'
    assert restored.job_id == 'job-object-1'
    assert restored.job_owner_pid == 654
    assert restored.tmux_socket_path == r'\\.\pipe\psmux-agent1'
    assert restored.summary_token() == (
        r'agent1:attached/healthy terminal=psmux runtime=psmux:%9 session=session-1 '
        r'runtime_root=C:\tmp\runtime '
        'pid=4321 job=job-object-1 owner=654'
    )


def test_runtime_snapshot_from_runtime_preserves_windows_binding_metadata() -> None:
    runtime = SimpleNamespace(
        agent_name='agent1',
        provider='codex',
        state='idle',
        health='healthy',
        workspace_path='/tmp/ws',
        runtime_ref='psmux:%9',
        session_ref='session-1',
        session_file=r'C:\tmp\agent1.session.json',
        session_id='session-1',
        lifecycle_state='idle',
        desired_state='mounted',
        reconcile_state='stable',
        binding_source='provider-session',
        terminal_backend='psmux',
        tmux_socket_name='psmux-agent1',
        tmux_socket_path=r'\\.\pipe\psmux-agent1',
        pane_id='%9',
        active_pane_id='%9',
        pane_state='alive',
        runtime_pid=4321,
        runtime_root=r'C:\tmp\runtime',
        job_id='job-object-1',
        job_owner_pid=654,
        last_failure_reason=None,
    )

    snapshot = CcbdRuntimeSnapshot.from_runtime(runtime)
    restored = CcbdRuntimeSnapshot.from_record(snapshot.to_record())

    assert restored.session_file == r'C:\tmp\agent1.session.json'
    assert restored.session_id == 'session-1'
    assert restored.job_id == 'job-object-1'
    assert restored.job_owner_pid == 654
    assert restored.tmux_socket_path == r'\\.\pipe\psmux-agent1'
    assert runtime_snapshots_summary((restored,)) == (
        r'agent1:idle/healthy terminal=psmux runtime=psmux:%9 session=session-1 '
        r'runtime_root=C:\tmp\runtime '
        'pid=4321 job=job-object-1 owner=654'
    )
