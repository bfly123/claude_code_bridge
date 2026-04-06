from __future__ import annotations

from storage.json_store import JsonStore
from storage.jsonl_store import JsonlStore
from storage.paths import PathLayout

from .models import ProjectNamespaceEvent, ProjectNamespaceState


class ProjectNamespaceStateStore:
    def __init__(self, layout: PathLayout, store: JsonStore | None = None) -> None:
        self._layout = layout
        self._store = store or JsonStore()

    def load(self) -> ProjectNamespaceState | None:
        path = self._layout.ccbd_state_path
        if not path.exists():
            return None
        return self._store.load(path, loader=ProjectNamespaceState.from_record)

    def save(self, state: ProjectNamespaceState) -> None:
        self._store.save(
            self._layout.ccbd_state_path,
            state,
            serializer=lambda value: value.to_record(),
        )


class ProjectNamespaceEventStore:
    def __init__(self, layout: PathLayout, store: JsonlStore | None = None) -> None:
        self._layout = layout
        self._store = store or JsonlStore()

    def append(self, event: ProjectNamespaceEvent) -> None:
        self._store.append(
            self._layout.ccbd_lifecycle_log_path,
            event,
            serializer=lambda value: value.to_record(),
        )

    def read_all(self) -> tuple[ProjectNamespaceEvent, ...]:
        rows = self._store.read_all(
            self._layout.ccbd_lifecycle_log_path,
            loader=ProjectNamespaceEvent.from_record,
        )
        return tuple(rows)

    def load_latest(self) -> ProjectNamespaceEvent | None:
        rows = self.read_all()
        return rows[-1] if rows else None


def next_namespace_epoch(current: ProjectNamespaceState | None) -> int:
    if current is None:
        return 1
    return current.namespace_epoch + 1


__all__ = ['ProjectNamespaceEventStore', 'ProjectNamespaceStateStore', 'next_namespace_epoch']
