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
        workspace_path=f"/tmp/{agent_name}",
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
    assert updated.last_restore_status is RestoreStatus.CHECKPOINT
    assert saved and saved[0][0] == "agent1"


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
