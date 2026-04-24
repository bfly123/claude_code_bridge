from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import cli.services.daemon as daemon_service
from ccbd.models import LeaseHealth
from ccbd.services.lifecycle import CcbdLifecycleStore, build_lifecycle
from cli.services.daemon_runtime.lifecycle import ensure_daemon_started as ensure_daemon_started_runtime
from cli.services.daemon_runtime.models import CcbdServiceError, DaemonHandle
from storage.paths import PathLayout


def test_lifecycle_store_roundtrip_preserves_startup_progress_fields(tmp_path: Path) -> None:
    project_root = tmp_path / 'repo-lifecycle-progress'
    layout = PathLayout(project_root)
    lifecycle = build_lifecycle(
        project_id='proj-1',
        occurred_at='2026-04-24T00:00:00Z',
        desired_state='running',
        phase='starting',
        generation=3,
        startup_id='startup-123',
        startup_stage='socket_listening',
        last_progress_at='2026-04-24T00:00:04Z',
        startup_deadline_at='2026-04-24T00:00:20Z',
        keeper_pid=111,
        socket_path=layout.ccbd_socket_path,
    )

    CcbdLifecycleStore(layout).save(lifecycle)
    loaded = CcbdLifecycleStore(layout).load()

    assert loaded == lifecycle


def test_ensure_daemon_started_can_wait_past_legacy_five_second_budget(monkeypatch) -> None:
    current = {'t': 0.0}

    def _now() -> float:
        return current['t']

    def _sleep(seconds: float) -> None:
        current['t'] += float(seconds)

    monkeypatch.setattr('cli.services.daemon_runtime.lifecycle.time.time', _now)
    monkeypatch.setattr('cli.services.daemon_runtime.lifecycle.time.sleep', _sleep)

    def _inspection():
        if current['t'] < 6.0:
            return SimpleNamespace(
                phase='starting',
                desired_state='running',
                health=LeaseHealth.UNMOUNTED,
                socket_connectable=False,
                reason='startup_in_progress',
                last_failure_reason=None,
                startup_stage='spawn_requested',
                last_progress_at='1970-01-01T00:00:00Z',
                startup_deadline_at='1970-01-01T00:00:20Z',
            )
        return SimpleNamespace(
            phase='mounted',
            desired_state='running',
            health=LeaseHealth.HEALTHY,
            socket_connectable=True,
            reason='healthy',
            last_failure_reason=None,
            startup_stage='mounted',
            last_progress_at='1970-01-01T00:00:06Z',
            startup_deadline_at=None,
        )

    handle = ensure_daemon_started_runtime(
        SimpleNamespace(),
        clear_shutdown_intent_fn=lambda context: None,
        record_running_intent_fn=lambda context: True,
        ensure_keeper_started_fn=lambda context: True,
        inspect_daemon_fn=lambda context: (None, None, _inspection()),
        connect_compatible_daemon_fn=lambda context, inspection, restart_on_mismatch: (
            DaemonHandle(client='ccbd-client', inspection=inspection, started=False)
            if inspection.phase == 'mounted'
            else None
        ),
        should_restart_unreachable_daemon_fn=lambda inspection: False,
        restart_unreachable_daemon_fn=lambda context, inspection: None,
        incompatible_daemon_error_fn=lambda: 'incompatible',
        start_timeout_s=20.0,
        progress_stall_timeout_s=0.0,
    )

    assert handle.client == 'ccbd-client'
    assert handle.started is True
    assert current['t'] >= 6.0
    assert current['t'] < 7.0


def test_ensure_daemon_started_uses_shared_startup_deadline(monkeypatch) -> None:
    current = {'t': 0.0}

    def _now() -> float:
        return current['t']

    def _sleep(seconds: float) -> None:
        current['t'] += float(seconds)

    monkeypatch.setattr('cli.services.daemon_runtime.lifecycle.time.time', _now)
    monkeypatch.setattr('cli.services.daemon_runtime.lifecycle.time.sleep', _sleep)

    inspection = SimpleNamespace(
        phase='starting',
        desired_state='running',
        health=LeaseHealth.UNMOUNTED,
        socket_connectable=False,
        reason='startup_in_progress',
        last_failure_reason=None,
        startup_stage='spawn_requested',
        last_progress_at='1970-01-01T00:00:00Z',
        startup_deadline_at='1970-01-01T00:00:08Z',
    )

    with pytest.raises(CcbdServiceError, match=r'lifecycle_starting\(stage=spawn_requested\)'):
        ensure_daemon_started_runtime(
            SimpleNamespace(),
            clear_shutdown_intent_fn=lambda context: None,
            record_running_intent_fn=lambda context: True,
            ensure_keeper_started_fn=lambda context: True,
            inspect_daemon_fn=lambda context: (None, None, inspection),
            connect_compatible_daemon_fn=lambda context, inspection, restart_on_mismatch: None,
            should_restart_unreachable_daemon_fn=lambda inspection: False,
            restart_unreachable_daemon_fn=lambda context, inspection: None,
            incompatible_daemon_error_fn=lambda: 'incompatible',
            start_timeout_s=20.0,
            progress_stall_timeout_s=0.0,
        )

    assert current['t'] >= 8.0
    assert current['t'] < 9.0


def test_connect_compatible_daemon_uses_short_control_plane_timeout(monkeypatch, tmp_path: Path) -> None:
    captured: list[float | None] = []

    class FakeClient:
        def __init__(self, socket_path, *, timeout_s=None) -> None:
            del socket_path
            self.timeout_s = timeout_s
            captured.append(timeout_s)

        def ping(self, target: str = 'ccbd') -> dict[str, object]:
            assert target == 'ccbd'
            return {'config_signature': 'sig'}

    monkeypatch.setattr(daemon_service, 'CcbdClient', FakeClient)
    monkeypatch.setattr(daemon_service, '_daemon_matches_project_config', lambda context, client: True)

    context = SimpleNamespace(paths=SimpleNamespace(ccbd_socket_path=tmp_path / 'ccbd.sock'))
    inspection = SimpleNamespace(socket_connectable=True, phase='mounted', health=LeaseHealth.HEALTHY)

    handle = daemon_service._connect_compatible_daemon(
        context,
        inspection,
        restart_on_mismatch=False,
    )

    assert handle is not None
    assert captured == [daemon_service.CONTROL_PLANE_RPC_TIMEOUT_S, None]
    assert handle.client.timeout_s is None
