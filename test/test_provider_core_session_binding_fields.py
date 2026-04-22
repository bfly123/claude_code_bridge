from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from provider_core.session_binding_evidence_runtime.fields import (
    session_job_id,
    session_job_owner_pid,
    session_runtime_pid,
    session_tmux_socket_name,
    session_tmux_socket_path,
)


def test_session_tmux_socket_fields_prefer_session_data(tmp_path: Path) -> None:
    session = SimpleNamespace(
        terminal='tmux',
        data={
            'tmux_socket_name': 'proj-sock',
            'tmux_socket_path': str(tmp_path / 'tmux.sock'),
        },
        backend=lambda: SimpleNamespace(_socket_name='backend-sock', _socket_path='/tmp/backend.sock'),
    )

    assert session_tmux_socket_name(session) == 'proj-sock'
    assert session_tmux_socket_path(session) == str(tmp_path / 'tmux.sock')


def test_session_tmux_socket_fields_support_psmux_sessions(tmp_path: Path) -> None:
    session = SimpleNamespace(
        terminal='psmux',
        data={},
        backend=lambda: SimpleNamespace(
            _socket_name='psmux-sock',
            _socket_path=str(tmp_path / 'psmux.pipe'),
        ),
    )

    assert session_tmux_socket_name(session) == 'psmux-sock'
    assert session_tmux_socket_path(session) == str(tmp_path / 'psmux.pipe')


def test_session_runtime_pid_prefers_data_then_provider_pid_file(tmp_path: Path) -> None:
    runtime_dir = tmp_path / 'runtime'
    runtime_dir.mkdir()
    (runtime_dir / 'codex.pid').write_text('123\n', encoding='utf-8')
    (runtime_dir / 'other.pid').write_text('456\n', encoding='utf-8')

    session = SimpleNamespace(runtime_dir=str(runtime_dir), data={})
    assert session_runtime_pid(session, provider='codex') == 123

    session_with_data = SimpleNamespace(runtime_dir=str(runtime_dir), data={'runtime_pid': '789'})
    assert session_runtime_pid(session_with_data, provider='codex') == 789


def test_session_job_fields_prefer_direct_value_then_session_data() -> None:
    session = SimpleNamespace(job_id='job-object-1', job_owner_pid=321, data={'job_id': 'ignored', 'job_owner_pid': '654'})

    assert session_job_id(session) == 'job-object-1'
    assert session_job_owner_pid(session) == 321

    data_only = SimpleNamespace(data={'job_id': 'job-object-2', 'job_owner_pid': '654'})

    assert session_job_id(data_only) == 'job-object-2'
    assert session_job_owner_pid(data_only) == 654


def test_session_job_id_falls_back_to_runtime_job_id_file(tmp_path: Path) -> None:
    runtime_dir = tmp_path / 'runtime'
    runtime_dir.mkdir()
    (runtime_dir / 'job.id').write_text('job-object-8\n', encoding='utf-8')

    session = SimpleNamespace(runtime_dir=str(runtime_dir), data={})

    assert session_job_id(session) == 'job-object-8'


def test_session_job_owner_pid_prefers_canonical_owner_pid_file(tmp_path: Path) -> None:
    runtime_dir = tmp_path / 'runtime'
    runtime_dir.mkdir()
    (runtime_dir / 'bridge.pid').write_text('777\n', encoding='utf-8')
    (runtime_dir / 'job-owner.pid').write_text('888\n', encoding='utf-8')

    session = SimpleNamespace(runtime_dir=str(runtime_dir), data={})

    assert session_job_owner_pid(session) == 888

