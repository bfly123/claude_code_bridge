from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from ccbd.models import SCHEMA_VERSION
from storage.json_store import JsonStore
from storage.jsonl_store import JsonlStore
from storage.paths import PathLayout

_NAMESPACE_STATE_RECORD_TYPE = 'ccbd_project_namespace_state'
_NAMESPACE_EVENT_RECORD_TYPE = 'ccbd_project_namespace_event'


def _clean_text(value: object) -> str | None:
    text = str(value or '').strip()
    return text or None


@dataclass(frozen=True)
class ProjectNamespaceState:
    project_id: str
    namespace_epoch: int
    tmux_socket_path: str
    tmux_session_name: str
    layout_version: int = 1
    layout_signature: str | None = None
    ui_attachable: bool = True
    last_started_at: str | None = None
    last_destroyed_at: str | None = None
    last_destroy_reason: str | None = None

    def __post_init__(self) -> None:
        if not str(self.project_id or '').strip():
            raise ValueError('project_id cannot be empty')
        if self.namespace_epoch <= 0:
            raise ValueError('namespace_epoch must be positive')
        if not str(self.tmux_socket_path or '').strip():
            raise ValueError('tmux_socket_path cannot be empty')
        if not str(self.tmux_session_name or '').strip():
            raise ValueError('tmux_session_name cannot be empty')
        if self.layout_version <= 0:
            raise ValueError('layout_version must be positive')
        if self.layout_signature is not None and not str(self.layout_signature).strip():
            raise ValueError('layout_signature cannot be blank when set')

    def with_started(self, *, occurred_at: str, ui_attachable: bool = True) -> ProjectNamespaceState:
        return replace(
            self,
            ui_attachable=bool(ui_attachable),
            last_started_at=str(occurred_at),
        )

    def with_destroyed(self, *, occurred_at: str, reason: str) -> ProjectNamespaceState:
        return replace(
            self,
            ui_attachable=False,
            last_destroyed_at=str(occurred_at),
            last_destroy_reason=str(reason or '').strip() or 'destroyed',
        )

    def to_record(self) -> dict[str, Any]:
        return {
            'schema_version': SCHEMA_VERSION,
            'record_type': _NAMESPACE_STATE_RECORD_TYPE,
            'project_id': self.project_id,
            'namespace_epoch': self.namespace_epoch,
            'tmux_socket_path': self.tmux_socket_path,
            'tmux_session_name': self.tmux_session_name,
            'layout_version': self.layout_version,
            'layout_signature': self.layout_signature,
            'ui_attachable': self.ui_attachable,
            'last_started_at': self.last_started_at,
            'last_destroyed_at': self.last_destroyed_at,
            'last_destroy_reason': self.last_destroy_reason,
        }

    @classmethod
    def from_record(cls, payload: dict[str, Any]) -> ProjectNamespaceState:
        if payload.get('schema_version') != SCHEMA_VERSION:
            raise ValueError(f'schema_version must be {SCHEMA_VERSION}')
        if payload.get('record_type') != _NAMESPACE_STATE_RECORD_TYPE:
            raise ValueError(f"record_type must be '{_NAMESPACE_STATE_RECORD_TYPE}'")
        return cls(
            project_id=str(payload['project_id']),
            namespace_epoch=int(payload['namespace_epoch']),
            tmux_socket_path=str(payload['tmux_socket_path']),
            tmux_session_name=str(payload['tmux_session_name']),
            layout_version=int(payload.get('layout_version', 1)),
            layout_signature=_clean_text(payload.get('layout_signature')),
            ui_attachable=bool(payload.get('ui_attachable', True)),
            last_started_at=_clean_text(payload.get('last_started_at')),
            last_destroyed_at=_clean_text(payload.get('last_destroyed_at')),
            last_destroy_reason=_clean_text(payload.get('last_destroy_reason')),
        )

    def summary_fields(self) -> dict[str, object]:
        return {
            'namespace_epoch': self.namespace_epoch,
            'namespace_tmux_socket_path': self.tmux_socket_path,
            'namespace_tmux_session_name': self.tmux_session_name,
            'namespace_layout_version': self.layout_version,
            'namespace_ui_attachable': self.ui_attachable,
            'namespace_last_started_at': self.last_started_at,
            'namespace_last_destroyed_at': self.last_destroyed_at,
            'namespace_last_destroy_reason': self.last_destroy_reason,
        }


@dataclass(frozen=True)
class ProjectNamespaceEvent:
    event_kind: str
    project_id: str
    occurred_at: str
    namespace_epoch: int | None = None
    tmux_socket_path: str | None = None
    tmux_session_name: str | None = None
    details: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.event_kind or '').strip():
            raise ValueError('event_kind cannot be empty')
        if not str(self.project_id or '').strip():
            raise ValueError('project_id cannot be empty')
        if not str(self.occurred_at or '').strip():
            raise ValueError('occurred_at cannot be empty')
        if self.namespace_epoch is not None and int(self.namespace_epoch) <= 0:
            raise ValueError('namespace_epoch must be positive when set')

    def to_record(self) -> dict[str, Any]:
        return {
            'schema_version': SCHEMA_VERSION,
            'record_type': _NAMESPACE_EVENT_RECORD_TYPE,
            'event_kind': self.event_kind,
            'project_id': self.project_id,
            'occurred_at': self.occurred_at,
            'namespace_epoch': self.namespace_epoch,
            'tmux_socket_path': self.tmux_socket_path,
            'tmux_session_name': self.tmux_session_name,
            'details': dict(self.details or {}),
        }

    @classmethod
    def from_record(cls, payload: dict[str, Any]) -> ProjectNamespaceEvent:
        if payload.get('schema_version') != SCHEMA_VERSION:
            raise ValueError(f'schema_version must be {SCHEMA_VERSION}')
        if payload.get('record_type') != _NAMESPACE_EVENT_RECORD_TYPE:
            raise ValueError(f"record_type must be '{_NAMESPACE_EVENT_RECORD_TYPE}'")
        details = payload.get('details') or {}
        if not isinstance(details, dict):
            raise ValueError('details must be an object')
        epoch = payload.get('namespace_epoch')
        return cls(
            event_kind=str(payload['event_kind']),
            project_id=str(payload['project_id']),
            occurred_at=str(payload['occurred_at']),
            namespace_epoch=int(epoch) if epoch is not None else None,
            tmux_socket_path=_clean_text(payload.get('tmux_socket_path')),
            tmux_session_name=_clean_text(payload.get('tmux_session_name')),
            details=dict(details),
        )

    def summary_fields(self) -> dict[str, object]:
        return {
            'namespace_last_event_kind': self.event_kind,
            'namespace_last_event_at': self.occurred_at,
            'namespace_last_event_epoch': self.namespace_epoch,
            'namespace_last_event_socket_path': self.tmux_socket_path,
            'namespace_last_event_session_name': self.tmux_session_name,
        }


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
        self._store.save(self._layout.ccbd_state_path, state, serializer=lambda value: value.to_record())


class ProjectNamespaceEventStore:
    def __init__(self, layout: PathLayout, store: JsonlStore | None = None) -> None:
        self._layout = layout
        self._store = store or JsonlStore()

    def append(self, event: ProjectNamespaceEvent) -> None:
        self._store.append(self._layout.ccbd_lifecycle_log_path, event, serializer=lambda value: value.to_record())

    def read_all(self) -> tuple[ProjectNamespaceEvent, ...]:
        rows = self._store.read_all(self._layout.ccbd_lifecycle_log_path, loader=ProjectNamespaceEvent.from_record)
        return tuple(rows)

    def load_latest(self) -> ProjectNamespaceEvent | None:
        rows = self.read_all()
        return rows[-1] if rows else None


def next_namespace_epoch(current: ProjectNamespaceState | None) -> int:
    if current is None:
        return 1
    return current.namespace_epoch + 1


__all__ = [
    'ProjectNamespaceEvent',
    'ProjectNamespaceEventStore',
    'ProjectNamespaceState',
    'ProjectNamespaceStateStore',
    'next_namespace_epoch',
]
