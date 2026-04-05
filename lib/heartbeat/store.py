from __future__ import annotations

from pathlib import Path

from storage.json_store import JsonStore
from storage.paths import PathLayout

from .models import HeartbeatState


class HeartbeatStateStore:
    def __init__(self, layout: PathLayout, store: JsonStore | None = None) -> None:
        self._layout = layout
        self._store = store or JsonStore()

    def load(self, subject_kind: str, subject_id: str) -> HeartbeatState | None:
        path = self._layout.heartbeat_subject_path(subject_kind, subject_id)
        if not path.exists():
            return None
        return self._store.load(path, loader=HeartbeatState.from_record)

    def save(self, state: HeartbeatState) -> None:
        self._store.save(
            self._layout.heartbeat_subject_path(state.subject_kind, state.subject_id),
            state,
            serializer=lambda value: value.to_record(),
        )

    def remove(self, subject_kind: str, subject_id: str) -> None:
        path = self._layout.heartbeat_subject_path(subject_kind, subject_id)
        try:
            path.unlink()
        except FileNotFoundError:
            return

    def list_all(self, subject_kind: str | None = None) -> list[HeartbeatState]:
        roots: list[Path]
        if subject_kind is None:
            root = self._layout.ccbd_heartbeats_dir
            if not root.exists():
                return []
            roots = [path for path in root.iterdir() if path.is_dir()]
        else:
            root = self._layout.heartbeat_subject_dir(subject_kind)
            if not root.exists():
                return []
            roots = [root]
        states: list[HeartbeatState] = []
        for directory in roots:
            for path in sorted(directory.glob('*.json')):
                states.append(self._store.load(path, loader=HeartbeatState.from_record))
        return states


__all__ = ['HeartbeatStateStore']
