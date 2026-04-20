from __future__ import annotations

from pathlib import Path

from completion.models import CompletionCursor
from storage.json_store import JsonStore
from storage.paths import PathLayout


class CursorStore:
    def __init__(self, layout: PathLayout, store: JsonStore | None = None) -> None:
        self._layout = layout
        self._store = store or JsonStore()

    def load(self, job_id: str) -> CompletionCursor | None:
        path = self._layout.cursor_path(job_id)
        if not path.exists():
            return None
        return self._store.load(path, loader=_completion_cursor_from_record)

    def save(self, job_id: str, cursor: CompletionCursor) -> Path:
        path = self._layout.cursor_path(job_id)
        self._store.save(path, cursor, serializer=lambda value: value.to_record())
        return path


def _completion_cursor_from_record(record: dict) -> CompletionCursor:
    source_kind = record['source_kind']
    if isinstance(source_kind, dict):
        source_kind = source_kind['value']
    from completion.models import CompletionSourceKind

    return CompletionCursor(
        source_kind=CompletionSourceKind(source_kind),
        opaque_cursor=record.get('opaque_cursor'),
        session_path=record.get('session_path'),
        offset=record.get('offset'),
        line_no=record.get('line_no'),
        event_seq=record.get('event_seq'),
        updated_at=record.get('updated_at'),
    )
