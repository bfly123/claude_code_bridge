from __future__ import annotations

from ccbd.ipc_state_store import CcbdIpcStateStore
from storage.paths import PathLayout


def test_ccbd_ipc_state_store_roundtrip(tmp_path) -> None:
    layout = PathLayout(tmp_path / 'repo')
    store = CcbdIpcStateStore(layout)

    store.save(
        ipc_kind='named_pipe',
        ipc_ref=r'\\.\pipe\ccb-test',
        backend_family='tmux',
        backend_impl='psmux',
        state='mounted',
        updated_at='2026-04-21T00:00:00Z',
    )

    assert store.load() == {
        'ipc_kind': 'named_pipe',
        'ipc_ref': r'\\.\pipe\ccb-test',
        'backend_family': 'tmux',
        'backend_impl': 'psmux',
        'state': 'mounted',
        'updated_at': '2026-04-21T00:00:00Z',
    }
