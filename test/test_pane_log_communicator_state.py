from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from provider_backends.pane_log_support.communicator_state import ensure_log_reader, initialize_state


def test_initialize_state_populates_runtime_fields(monkeypatch, tmp_path: Path) -> None:
    session_info = {
        'ccb_session_id': 'ccb-pane-1',
        '_session_file': str(tmp_path / '.ccb' / '.pane-session'),
        'pane_title_marker': 'agent5',
    }
    comm = SimpleNamespace(
        sync_timeout_env='PANE_SYNC_TIMEOUT',
        missing_session_message='missing',
        _load_session_info=lambda: dict(session_info),
    )
    monkeypatch.setenv('PANE_SYNC_TIMEOUT', '33')

    initialize_state(
        comm,
        get_pane_id_from_session_fn=lambda info: '%11',
        get_backend_for_session_fn=lambda info: 'backend:tmux',
    )

    assert comm.ccb_session_id == 'ccb-pane-1'
    assert comm.terminal == 'tmux'
    assert comm.pane_id == '%11'
    assert comm.backend == 'backend:tmux'
    assert comm.timeout == 33
    assert comm.project_session_file == session_info['_session_file']
    assert comm._log_reader is None
    assert comm._log_reader_primed is False


def test_ensure_log_reader_uses_explicit_or_runtime_log_path(tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []

    class Reader:
        def __init__(self, *, work_dir, pane_log_path) -> None:
            calls.append({'work_dir': work_dir, 'pane_log_path': pane_log_path})

    comm = SimpleNamespace(
        session_info={
            'work_dir': str(tmp_path / 'workspace'),
            'pane_log_path': str(tmp_path / 'logs' / 'pane.log'),
            'runtime_dir': str(tmp_path / 'runtime'),
        },
        _log_reader=None,
        _log_reader_primed=False,
    )

    ensure_log_reader(comm, reader_cls=Reader)

    assert calls == [
        {
            'work_dir': tmp_path / 'workspace',
            'pane_log_path': tmp_path / 'logs' / 'pane.log',
        }
    ]
    assert comm._log_reader_primed is True
