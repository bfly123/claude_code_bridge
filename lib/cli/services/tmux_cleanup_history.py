from __future__ import annotations

from dataclasses import dataclass

from storage.jsonl_store import JsonlStore
from storage.paths import PathLayout

from .tmux_project_cleanup import ProjectTmuxCleanupSummary

_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class TmuxCleanupEvent:
    event_kind: str
    project_id: str
    occurred_at: str
    summaries: tuple[ProjectTmuxCleanupSummary, ...]

    def to_record(self) -> dict[str, object]:
        return {
            'schema_version': _SCHEMA_VERSION,
            'record_type': 'tmux_cleanup_event',
            'event_kind': self.event_kind,
            'project_id': self.project_id,
            'occurred_at': self.occurred_at,
            'summaries': [
                {
                    'socket_name': item.socket_name,
                    'owned_panes': list(item.owned_panes),
                    'active_panes': list(item.active_panes),
                    'orphaned_panes': list(item.orphaned_panes),
                    'killed_panes': list(item.killed_panes),
                }
                for item in self.summaries
            ],
        }

    @classmethod
    def from_record(cls, record: dict[str, object]) -> TmuxCleanupEvent:
        if int(record.get('schema_version') or 0) != _SCHEMA_VERSION:
            raise ValueError('invalid schema_version for tmux cleanup event')
        if record.get('record_type') != 'tmux_cleanup_event':
            raise ValueError('invalid record_type for tmux cleanup event')
        raw_summaries = record.get('summaries') or []
        if not isinstance(raw_summaries, list):
            raise ValueError('summaries must be a list')
        summaries: list[ProjectTmuxCleanupSummary] = []
        for raw in raw_summaries:
            if not isinstance(raw, dict):
                raise ValueError('summary rows must be objects')
            summaries.append(
                ProjectTmuxCleanupSummary(
                    socket_name=_clean(raw.get('socket_name')),
                    owned_panes=_tuple(raw.get('owned_panes')),
                    active_panes=_tuple(raw.get('active_panes')),
                    orphaned_panes=_tuple(raw.get('orphaned_panes')),
                    killed_panes=_tuple(raw.get('killed_panes')),
                )
            )
        return cls(
            event_kind=str(record.get('event_kind') or '').strip() or 'unknown',
            project_id=str(record.get('project_id') or '').strip(),
            occurred_at=str(record.get('occurred_at') or '').strip(),
            summaries=tuple(summaries),
        )

    def summary_fields(self) -> dict[str, object]:
        total_owned = sum(len(item.owned_panes) for item in self.summaries)
        total_active = sum(len(item.active_panes) for item in self.summaries)
        total_orphaned = sum(len(item.orphaned_panes) for item in self.summaries)
        total_killed = sum(len(item.killed_panes) for item in self.summaries)
        sockets = [item.socket_name for item in self.summaries if item.socket_name]
        return {
            'tmux_cleanup_last_kind': self.event_kind,
            'tmux_cleanup_last_at': self.occurred_at,
            'tmux_cleanup_socket_count': len(self.summaries),
            'tmux_cleanup_total_owned': total_owned,
            'tmux_cleanup_total_active': total_active,
            'tmux_cleanup_total_orphaned': total_orphaned,
            'tmux_cleanup_total_killed': total_killed,
            'tmux_cleanup_sockets': sockets,
        }


class TmuxCleanupHistoryStore:
    def __init__(self, layout: PathLayout, store: JsonlStore | None = None) -> None:
        self._layout = layout
        self._store = store or JsonlStore()

    def append(self, event: TmuxCleanupEvent) -> None:
        self._store.append(self._layout.ccbd_tmux_cleanup_history_path, event, serializer=lambda value: value.to_record())

    def load_latest(self) -> TmuxCleanupEvent | None:
        rows = self._store.read_all(self._layout.ccbd_tmux_cleanup_history_path, loader=TmuxCleanupEvent.from_record)
        if not rows:
            return None
        return rows[-1]


def _tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


def _clean(value: object) -> str | None:
    text = str(value or '').strip()
    return text or None


__all__ = ['TmuxCleanupEvent', 'TmuxCleanupHistoryStore']
