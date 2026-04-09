from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from provider_core.session_binding_evidence_runtime.fields import (
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


def test_session_runtime_pid_prefers_data_then_provider_pid_file(tmp_path: Path) -> None:
    runtime_dir = tmp_path / 'runtime'
    runtime_dir.mkdir()
    (runtime_dir / 'codex.pid').write_text('123\n', encoding='utf-8')
    (runtime_dir / 'other.pid').write_text('456\n', encoding='utf-8')

    session = SimpleNamespace(runtime_dir=str(runtime_dir), data={})
    assert session_runtime_pid(session, provider='codex') == 123

    session_with_data = SimpleNamespace(runtime_dir=str(runtime_dir), data={'runtime_pid': '789'})
    assert session_runtime_pid(session_with_data, provider='codex') == 789

