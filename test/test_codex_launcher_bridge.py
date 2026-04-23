from __future__ import annotations

from pathlib import Path

from provider_backends.codex.launcher_runtime.bridge import ensure_windows_job_object, post_launch


def test_ensure_windows_job_object_assigns_named_job_on_windows(tmp_path: Path) -> None:
    seen: list[tuple[str, int]] = []

    job_id = ensure_windows_job_object(
        runtime_dir=tmp_path,
        pids=(4321, 4321, 8765),
        os_name='nt',
        assign_process_to_named_job_fn=lambda job_name, pid: seen.append((job_name, pid)) or True,
        job_name_fn=lambda runtime_dir: 'Local\\ccb-job-1',
    )

    assert job_id == 'Local\\ccb-job-1'
    assert seen == [('Local\\ccb-job-1', 4321), ('Local\\ccb-job-1', 8765)]


def test_ensure_windows_job_object_requires_all_pid_assignments(tmp_path: Path) -> None:
    attempts: list[int] = []

    job_id = ensure_windows_job_object(
        runtime_dir=tmp_path,
        pids=(4321, 8765),
        os_name='nt',
        assign_process_to_named_job_fn=lambda job_name, pid: attempts.append(pid) or pid == 4321,
        job_name_fn=lambda runtime_dir: 'Local\\ccb-job-1',
    )

    assert job_id is None
    assert attempts == [4321, 8765]


def test_post_launch_prefers_windows_job_object_name(tmp_path: Path, monkeypatch) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        'provider_backends.codex.launcher_runtime.bridge.write_pane_pid',
        lambda backend, pane_id, path: 123,
    )
    monkeypatch.setattr(
        'provider_backends.codex.launcher_runtime.bridge.spawn_codex_bridge',
        lambda *, runtime_dir, pane_id: 456,
    )
    monkeypatch.setattr(
        'provider_backends.codex.launcher_runtime.bridge.ensure_windows_job_object',
        lambda *, runtime_dir, pids: 'Local\\ccb-job-2',
    )
    monkeypatch.setattr(
        'provider_backends.codex.launcher_runtime.bridge.update_runtime_session_payload',
        lambda runtime_dir, **kwargs: captured.update(kwargs) or kwargs,
    )

    post_launch(
        backend=object(),
        pane_id='%9',
        runtime_dir=tmp_path,
        launch_session_id='launch-1',
        prepared_state={'job_id': 'prepared-job-id'},
    )

    assert captured['job_id'] == 'Local\\ccb-job-2'
    assert captured['runtime_pid'] == 123
    assert captured['job_owner_pid'] == 456


def test_post_launch_preserves_prepared_job_id_when_windows_job_object_missing(tmp_path: Path, monkeypatch) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        'provider_backends.codex.launcher_runtime.bridge.write_pane_pid',
        lambda backend, pane_id, path: 123,
    )
    monkeypatch.setattr(
        'provider_backends.codex.launcher_runtime.bridge.spawn_codex_bridge',
        lambda *, runtime_dir, pane_id: 456,
    )
    monkeypatch.setattr(
        'provider_backends.codex.launcher_runtime.bridge.ensure_windows_job_object',
        lambda *, runtime_dir, pids: None,
    )
    monkeypatch.setattr(
        'provider_backends.codex.launcher_runtime.bridge.update_runtime_session_payload',
        lambda runtime_dir, **kwargs: captured.update(kwargs) or kwargs,
    )

    post_launch(
        backend=object(),
        pane_id='%9',
        runtime_dir=tmp_path,
        launch_session_id='launch-1',
        prepared_state={'job_id': 'prepared-job-id'},
    )

    assert captured['job_id'] == 'prepared-job-id'
    assert captured['runtime_pid'] == 123
    assert captured['job_owner_pid'] == 456
