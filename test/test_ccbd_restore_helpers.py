from __future__ import annotations

from types import SimpleNamespace

import pytest

from agents.models import (
    AgentRestoreState,
    AgentState,
    AgentValidationError,
    RestoreMode,
    RestoreStatus,
    RuntimeBindingSource,
)
from ccbd.api_models import TargetKind
from ccbd.models import CcbdRestoreEntry
from ccbd.services.dispatcher_runtime.lifecycle_start_runtime.models import QueuedTargetSlot
from ccbd.services.dispatcher_runtime.lifecycle_start_runtime.recovery import (
    iter_runnable_agent_slots,
    refresh_slot_runtime_for_start,
)
from ccbd.services.dispatcher_runtime.restore import build_last_restore_report
from ccbd.services.runtime_runtime.restore import ensure_runtime_ready, restore_runtime


def _runtime(
    agent_name: str,
    *,
    state=AgentState.DEGRADED,
    health: str = "pane-dead",
    backend_type: str = "pane-backed",
):
    return SimpleNamespace(
        agent_name=agent_name,
        state=state,
        health=health,
        backend_type=backend_type,
        pid=123,
        runtime_ref="runtime-ref",
        session_ref="session-ref",
        job_id='job-object-1',
        job_owner_pid=654,
        provider='codex',
        runtime_root='/tmp/runtime-root',
        runtime_pid=456,
        terminal_backend='psmux',
        pane_id='%9',
        active_pane_id='%9',
        pane_title_marker='agent1',
        pane_state='alive',
        tmux_socket_name='sock-1',
        tmux_socket_path=r'\\.\pipe\psmux-agent1',
        session_file=f"/tmp/{agent_name}.session.json",
        session_id=f'{agent_name}-session-id',
        slot_key=agent_name,
        window_id='@3',
        workspace_epoch=4,
        workspace_path=f"/tmp/{agent_name}",
        lifecycle_state='idle',
        managed_by='external',
        binding_source=RuntimeBindingSource.PROVIDER_SESSION,
    )


def test_refresh_slot_runtime_for_start_recovers_refreshable_degraded_runtime() -> None:
    refreshed = _runtime("agent1", state=AgentState.IDLE, health="healthy")
    dispatcher = SimpleNamespace(
        _execution_service=object(),
        _runtime_service=SimpleNamespace(refresh_provider_binding=lambda agent_name, recover: refreshed),
        _registry=SimpleNamespace(spec_for=lambda agent_name: SimpleNamespace(provider="codex")),
        _provider_catalog=SimpleNamespace(get=lambda provider: SimpleNamespace(supports_resume=True)),
    )
    slot = QueuedTargetSlot(target_kind=TargetKind.AGENT, target_name="agent1", runtime=_runtime("agent1"))

    updated = refresh_slot_runtime_for_start(dispatcher, slot)

    assert updated is not None
    assert updated.runtime is refreshed


def test_iter_runnable_agent_slots_skips_blocked_degraded_runtime() -> None:
    blocked = _runtime("agent1", health="session-missing")
    idle = _runtime("agent2", state=AgentState.IDLE, health="healthy")
    dispatcher = SimpleNamespace(
        _config=SimpleNamespace(agents=("agent1", "agent2")),
        _state=SimpleNamespace(
            active_job=lambda agent_name: None,
            queue_depth=lambda agent_name: 1,
        ),
        _registry=SimpleNamespace(get=lambda agent_name: blocked if agent_name == "agent1" else idle),
        _execution_service=object(),
        _runtime_service=object(),
        _provider_catalog=SimpleNamespace(get=lambda provider: SimpleNamespace(supports_resume=True)),
    )

    slots = list(iter_runnable_agent_slots(dispatcher))

    assert [slot.target_name for slot in slots] == ["agent2"]


def test_restore_runtime_updates_restore_state_and_attaches_when_runtime_inactive() -> None:
    restore_state = AgentRestoreState(
        restore_mode=RestoreMode.AUTO,
        last_checkpoint="checkpoint-1",
        conversation_summary="resume",
        last_restore_status=None,
    )
    saved: list[tuple[str, object]] = []
    attached: list[dict] = []
    registry = SimpleNamespace(
        spec_for=lambda agent_name: SimpleNamespace(name=agent_name, runtime_mode=SimpleNamespace(value="pane-backed")),
        get=lambda agent_name: None,
    )
    restore_store = SimpleNamespace(
        load=lambda agent_name: restore_state,
        save=lambda agent_name, state: saved.append((agent_name, state)),
    )

    updated = restore_runtime(
        layout=SimpleNamespace(workspace_path=lambda agent_name: f"/tmp/{agent_name}"),
        registry=registry,
        restore_store=restore_store,
        attach_runtime_fn=lambda **kwargs: attached.append(kwargs),
        clock=lambda: "2026-04-06T00:00:00Z",
        agent_name="agent1",
    )

    assert attached and attached[0]["health"] == "restored"
    assert attached[0]["job_id"] is None
    assert attached[0]["job_owner_pid"] is None
    assert updated.last_restore_status is RestoreStatus.CHECKPOINT
    assert saved and saved[0][0] == "agent1"


def test_ensure_runtime_ready_preserves_runtime_job_metadata_when_reattaching() -> None:
    runtime = _runtime("agent1", state=AgentState.STOPPED, health="restored")
    attached: list[dict] = []
    registry = SimpleNamespace(
        spec_for=lambda agent_name: SimpleNamespace(name=agent_name, runtime_mode=SimpleNamespace(value="pane-backed")),
        get=lambda agent_name: runtime,
    )
    restore_store = SimpleNamespace(load=lambda agent_name: None)

    ensure_runtime_ready(
        layout=SimpleNamespace(workspace_path=lambda agent_name: f"/tmp/{agent_name}"),
        registry=registry,
        restore_store=restore_store,
        attach_runtime_fn=lambda **kwargs: attached.append(kwargs) or SimpleNamespace(**kwargs),
        restore_runtime_fn=lambda agent_name: None,
        clock=lambda: "2026-04-06T00:00:00Z",
        agent_name="agent1",
    )

    assert attached[0]["job_id"] == "job-object-1"
    assert attached[0]["job_owner_pid"] == 654
    assert attached[0]["provider"] == 'codex'
    assert attached[0]["runtime_root"] == '/tmp/runtime-root'
    assert attached[0]["runtime_pid"] == 456
    assert attached[0]["terminal_backend"] == 'psmux'
    assert attached[0]["pane_id"] == '%9'
    assert attached[0]["active_pane_id"] == '%9'
    assert attached[0]["pane_title_marker"] == 'agent1'
    assert attached[0]["pane_state"] == 'alive'
    assert attached[0]["tmux_socket_name"] == 'sock-1'
    assert attached[0]["tmux_socket_path"] == r'\\.\pipe\psmux-agent1'
    assert attached[0]["session_file"] == '/tmp/agent1.session.json'
    assert attached[0]["session_id"] == 'agent1-session-id'
    assert attached[0]["window_id"] == '@3'
    assert attached[0]["workspace_epoch"] == 4
    assert attached[0]["lifecycle_state"] == 'idle'
    assert attached[0]["managed_by"] == 'external'


def test_restore_runtime_preserves_runtime_binding_metadata_when_reattaching() -> None:
    restore_state = AgentRestoreState(
        restore_mode=RestoreMode.AUTO,
        last_checkpoint='checkpoint-1',
        conversation_summary='resume',
        last_restore_status=None,
    )
    runtime = _runtime('agent1', state=AgentState.STOPPED, health='pane-missing')
    attached: list[dict] = []
    registry = SimpleNamespace(
        spec_for=lambda agent_name: SimpleNamespace(name=agent_name, runtime_mode=SimpleNamespace(value='pane-backed')),
        get=lambda agent_name: runtime,
    )
    restore_store = SimpleNamespace(
        load=lambda agent_name: restore_state,
        save=lambda agent_name, state: None,
    )

    restore_runtime(
        layout=SimpleNamespace(workspace_path=lambda agent_name: f"/tmp/{agent_name}"),
        registry=registry,
        restore_store=restore_store,
        attach_runtime_fn=lambda **kwargs: attached.append(kwargs),
        clock=lambda: '2026-04-06T00:00:00Z',
        agent_name='agent1',
    )

    assert attached[0]['health'] == 'restored'
    assert attached[0]['provider'] == 'codex'
    assert attached[0]['runtime_root'] == '/tmp/runtime-root'
    assert attached[0]['runtime_pid'] == 456
    assert attached[0]['terminal_backend'] == 'psmux'
    assert attached[0]['pane_id'] == '%9'
    assert attached[0]['active_pane_id'] == '%9'
    assert attached[0]['pane_title_marker'] == 'agent1'
    assert attached[0]['pane_state'] == 'alive'
    assert attached[0]['tmux_socket_name'] == 'sock-1'
    assert attached[0]['tmux_socket_path'] == r'\\.\pipe\psmux-agent1'
    assert attached[0]['session_file'] == '/tmp/agent1.session.json'
    assert attached[0]['session_id'] == 'agent1-session-id'
    assert attached[0]['job_id'] == 'job-object-1'
    assert attached[0]['job_owner_pid'] == 654


def test_ensure_runtime_ready_raises_without_runtime_or_restore_state() -> None:
    registry = SimpleNamespace(
        spec_for=lambda agent_name: SimpleNamespace(name=agent_name, runtime_mode=SimpleNamespace(value="pane-backed")),
        get=lambda agent_name: None,
    )
    restore_store = SimpleNamespace(load=lambda agent_name: None)

    with pytest.raises(AgentValidationError, match="start it first"):
        ensure_runtime_ready(
            layout=SimpleNamespace(workspace_path=lambda agent_name: f"/tmp/{agent_name}"),
            registry=registry,
            restore_store=restore_store,
            attach_runtime_fn=lambda **kwargs: None,
            restore_runtime_fn=lambda agent_name: None,
            clock=lambda: "2026-04-06T00:00:00Z",
            agent_name="agent1",
        )


def test_build_last_restore_report_counts_entries() -> None:
    dispatcher = SimpleNamespace(
        _last_restore_generated_at="2026-04-06T00:00:00Z",
        _last_restore_entries=(
            CcbdRestoreEntry(
                job_id="job-1",
                agent_name="agent1",
                provider="codex",
                status="restored",
                reason="ok",
                resume_capable=True,
            ),
            CcbdRestoreEntry(
                job_id="job-2",
                agent_name="agent2",
                provider="claude",
                status="terminal_pending",
                reason="done",
                resume_capable=True,
            ),
        ),
        _clock=lambda: "2026-04-06T00:00:01Z",
    )

    report = build_last_restore_report(dispatcher, project_id="project-1")

    assert report.running_job_count == 2
    assert report.restored_execution_count == 1
    assert report.terminal_pending_count == 1


def test_build_last_restore_report_preserves_runtime_binding_metadata() -> None:
    dispatcher = SimpleNamespace(
        _last_restore_generated_at="2026-04-06T00:00:00Z",
        _last_restore_entries=(
            CcbdRestoreEntry(
                job_id="job-1",
                agent_name="agent1",
                provider="codex",
                status="restored",
                reason="provider_resumed",
                resume_capable=True,
                runtime_ref="psmux:%9",
                session_id="sid-demo",
                terminal_backend="psmux",
                runtime_root=r"C:\tmp\runtime-agent1",
                runtime_pid=4321,
                runtime_job_id="job-object-1",
                job_owner_pid=654,
            ),
        ),
        _clock=lambda: "2026-04-06T00:00:01Z",
    )

    report = build_last_restore_report(dispatcher, project_id="project-1")

    assert report.entries[0].runtime_root == r"C:\tmp\runtime-agent1"
    assert report.entries[0].runtime_job_id == "job-object-1"
    assert report.summary_fields()["last_restore_results_text"] == (
        r"agent1/codex:restored(provider_resumed) terminal=psmux runtime=psmux:%9 "
        r"session=sid-demo runtime_root=C:\tmp\runtime-agent1 pid=4321 job=job-object-1 owner=654"
    )
