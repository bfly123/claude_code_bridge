from __future__ import annotations

from storage.json_store import JsonStore
from storage.paths import PathLayout


class CcbdIpcStateStore:
    def __init__(self, layout: PathLayout, store: JsonStore | None = None) -> None:
        self._layout = layout
        self._store = store or JsonStore()

    def load(self) -> dict[str, object] | None:
        path = self._layout.ccbd_ipc_path
        if not path.exists():
            return None
        payload = self._store.load(path)
        return dict(payload)

    def save(
        self,
        *,
        ipc_kind: str,
        ipc_ref: str,
        backend_family: str | None,
        backend_impl: str | None,
        state: str,
        updated_at: str,
    ) -> None:
        self._store.save(
            self._layout.ccbd_ipc_path,
            {
                'ipc_kind': str(ipc_kind or '').strip(),
                'ipc_ref': str(ipc_ref or '').strip(),
                'backend_family': str(backend_family or '').strip() or None,
                'backend_impl': str(backend_impl or '').strip() or None,
                'state': str(state or '').strip() or 'unknown',
                'updated_at': str(updated_at or '').strip(),
            },
        )


__all__ = ['CcbdIpcStateStore']
