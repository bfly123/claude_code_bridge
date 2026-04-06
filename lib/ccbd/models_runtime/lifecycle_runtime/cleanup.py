from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ccbd.models_runtime.lifecycle_runtime.common import clean_text, clean_tuple


@dataclass(frozen=True)
class CcbdTmuxCleanupSummary:
    socket_name: str | None
    owned_panes: tuple[str, ...] = ()
    active_panes: tuple[str, ...] = ()
    orphaned_panes: tuple[str, ...] = ()
    killed_panes: tuple[str, ...] = ()

    def to_record(self) -> dict[str, Any]:
        return {
            'socket_name': self.socket_name,
            'owned_panes': list(self.owned_panes),
            'active_panes': list(self.active_panes),
            'orphaned_panes': list(self.orphaned_panes),
            'killed_panes': list(self.killed_panes),
        }

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> 'CcbdTmuxCleanupSummary':
        return cls(
            socket_name=clean_text(record.get('socket_name')),
            owned_panes=clean_tuple(record.get('owned_panes')),
            active_panes=clean_tuple(record.get('active_panes')),
            orphaned_panes=clean_tuple(record.get('orphaned_panes')),
            killed_panes=clean_tuple(record.get('killed_panes')),
        )

    @classmethod
    def from_summary_object(cls, value: object) -> 'CcbdTmuxCleanupSummary':
        return cls(
            socket_name=clean_text(getattr(value, 'socket_name', None)),
            owned_panes=tuple(str(item).strip() for item in getattr(value, 'owned_panes', ()) if str(item).strip()),
            active_panes=tuple(str(item).strip() for item in getattr(value, 'active_panes', ()) if str(item).strip()),
            orphaned_panes=tuple(str(item).strip() for item in getattr(value, 'orphaned_panes', ()) if str(item).strip()),
            killed_panes=tuple(str(item).strip() for item in getattr(value, 'killed_panes', ()) if str(item).strip()),
        )


def cleanup_summaries_from_objects(items: object) -> tuple[CcbdTmuxCleanupSummary, ...]:
    values = items or ()
    return tuple(CcbdTmuxCleanupSummary.from_summary_object(item) for item in values)


__all__ = ['CcbdTmuxCleanupSummary', 'cleanup_summaries_from_objects']
