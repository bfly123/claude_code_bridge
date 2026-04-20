from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from provider_backends.droid.comm_runtime.communicator_state import ensure_log_reader, initialize_state


def test_initialize_state_populates_runtime_fields(monkeypatch, tmp_path: Path) -> None:
    session_info = {
        'ccb_session_id': 'ccb-droid-1',
        '_session_file': str(tmp_path / '.ccb' / '.droid-session'),
        'pane_title_marker': 'agent4',
    }
    comm = SimpleNamespace(_load_session_info=lambda: dict(session_info))
    monkeypatch.setenv('DROID_SYNC_TIMEOUT', '45')

    initialize_state(
        comm,
        get_pane_id_from_session_fn=lambda info: '%8',
        get_backend_for_session_fn=lambda info: 'backend:tmux',
    )

    assert comm.ccb_session_id == 'ccb-droid-1'
    assert comm.terminal == 'tmux'
    assert comm.pane_id == '%8'
    assert comm.backend == 'backend:tmux'
    assert comm.timeout == 45
    assert comm.project_session_file == session_info['_session_file']
    assert comm.marker_prefix == 'droid'
    assert comm._log_reader is None
    assert comm._log_reader_primed is False


def test_ensure_log_reader_primes_once(tmp_path: Path) -> None:
    calls: list[str] = []
    reader_calls: list[dict[str, object]] = []

    class Reader:
        def __init__(self, *, work_dir) -> None:
            reader_calls.append({'work_dir': work_dir})

        def set_preferred_session(self, path) -> None:
            reader_calls.append({'preferred': path})

        def set_session_id_hint(self, session_id) -> None:
            reader_calls.append({'session_id': session_id})

    comm = SimpleNamespace(
        session_info={
            'work_dir': str(tmp_path / 'workspace'),
            'droid_session_path': str(tmp_path / 'sessions' / 's1.json'),
            'droid_session_id': 'sid-1',
        },
        _log_reader=None,
        _log_reader_primed=False,
        _prime_log_binding=lambda: calls.append('prime'),
    )

    ensure_log_reader(comm, log_reader_cls=Reader)
    ensure_log_reader(comm, log_reader_cls=Reader)

    assert len(calls) == 1
    assert reader_calls[0]['work_dir'] == tmp_path / 'workspace'
    assert reader_calls[1]['preferred'] == tmp_path / 'sessions' / 's1.json'
    assert reader_calls[2]['session_id'] == 'sid-1'
