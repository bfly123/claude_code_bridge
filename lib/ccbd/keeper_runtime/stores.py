from __future__ import annotations

from storage.json_store import JsonStore
from storage.paths import PathLayout

from .records import KeeperState, ShutdownIntent


class KeeperStateStore:
    def __init__(self, layout: PathLayout, store: JsonStore | None = None) -> None:
        self._layout = layout
        self._store = store or JsonStore()

    def load(self) -> KeeperState | None:
        path = self._layout.ccbd_keeper_path
        if not path.exists():
            return None
        return self._store.load(path, loader=KeeperState.from_record)

    def save(self, state: KeeperState) -> None:
        self._store.save(self._layout.ccbd_keeper_path, state, serializer=lambda value: value.to_record())


class ShutdownIntentStore:
    def __init__(self, layout: PathLayout, store: JsonStore | None = None) -> None:
        self._layout = layout
        self._store = store or JsonStore()

    def load(self) -> ShutdownIntent | None:
        path = self._layout.ccbd_shutdown_intent_path
        if not path.exists():
            return None
        return self._store.load(path, loader=ShutdownIntent.from_record)

    def save(self, intent: ShutdownIntent) -> None:
        self._store.save(self._layout.ccbd_shutdown_intent_path, intent, serializer=lambda value: value.to_record())

    def clear(self) -> None:
        try:
            self._layout.ccbd_shutdown_intent_path.unlink()
        except FileNotFoundError:
            pass


__all__ = ['KeeperStateStore', 'ShutdownIntentStore']
