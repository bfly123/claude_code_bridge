from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from ccbd.models import SCHEMA_VERSION

from .common import (
    NAMESPACE_EVENT_RECORD_TYPE,
    NAMESPACE_STATE_RECORD_TYPE,
    clean_text,
    require_record_type,
    require_schema_version,
)


@dataclass(frozen=True)
class ProjectNamespaceState:
    project_id: str
    namespace_epoch: int
    tmux_socket_path: str
    tmux_session_name: str
    layout_version: int = 1
    layout_signature: str | None = None
    control_window_name: str | None = None
    control_window_id: str | None = None
    workspace_window_name: str | None = None
    workspace_window_id: str | None = None
    workspace_epoch: int = 1
    ui_attachable: bool = True
    last_started_at: str | None = None
    last_destroyed_at: str | None = None
    last_destroy_reason: str | None = None
    backend_family: str | None = None
    backend_impl: str | None = None

    @property
    def backend_ref(self) -> str:
        return self.tmux_socket_path

    @property
    def session_name(self) -> str:
        return self.tmux_session_name

    @property
    def workspace_name(self) -> str | None:
        return self.workspace_window_name

    def __post_init__(self) -> None:
        require_non_empty_text(self.project_id, field_name='project_id')
        require_positive_int(self.namespace_epoch, field_name='namespace_epoch')
        require_non_empty_text(self.tmux_socket_path, field_name='tmux_socket_path')
        require_non_empty_text(self.tmux_session_name, field_name='tmux_session_name')
        require_positive_int(self.layout_version, field_name='layout_version')
        if self.layout_signature is not None:
            require_non_empty_text(self.layout_signature, field_name='layout_signature')
        if self.control_window_name is not None:
            require_non_empty_text(self.control_window_name, field_name='control_window_name')
        if self.control_window_id is not None:
            require_non_empty_text(self.control_window_id, field_name='control_window_id')
        if self.workspace_window_name is not None:
            require_non_empty_text(self.workspace_window_name, field_name='workspace_window_name')
        if self.workspace_window_id is not None:
            require_non_empty_text(self.workspace_window_id, field_name='workspace_window_id')
        require_positive_int(self.workspace_epoch, field_name='workspace_epoch')
        if self.backend_family is not None:
            require_non_empty_text(self.backend_family, field_name='backend_family')
        if self.backend_impl is not None:
            require_non_empty_text(self.backend_impl, field_name='backend_impl')

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
            'record_type': NAMESPACE_STATE_RECORD_TYPE,
            'project_id': self.project_id,
            'namespace_epoch': self.namespace_epoch,
            'tmux_socket_path': self.tmux_socket_path,
            'tmux_session_name': self.tmux_session_name,
            'layout_version': self.layout_version,
            'layout_signature': self.layout_signature,
            'control_window_name': self.control_window_name,
            'control_window_id': self.control_window_id,
            'workspace_window_name': self.workspace_window_name,
            'workspace_window_id': self.workspace_window_id,
            'workspace_epoch': self.workspace_epoch,
            'ui_attachable': self.ui_attachable,
            'last_started_at': self.last_started_at,
            'last_destroyed_at': self.last_destroyed_at,
            'last_destroy_reason': self.last_destroy_reason,
            'backend_family': self.backend_family,
            'backend_impl': self.backend_impl,
        }

    @classmethod
    def from_record(cls, payload: dict[str, Any]) -> ProjectNamespaceState:
        require_schema_version(payload)
        require_record_type(payload, record_type=NAMESPACE_STATE_RECORD_TYPE)
        return cls(
            project_id=str(payload['project_id']),
            namespace_epoch=int(payload['namespace_epoch']),
            tmux_socket_path=str(payload['tmux_socket_path']),
            tmux_session_name=str(payload['tmux_session_name']),
            layout_version=int(payload.get('layout_version', 1)),
            layout_signature=clean_text(payload.get('layout_signature')),
            control_window_name=clean_text(payload.get('control_window_name')),
            control_window_id=clean_text(payload.get('control_window_id')),
            workspace_window_name=clean_text(payload.get('workspace_window_name')),
            workspace_window_id=clean_text(payload.get('workspace_window_id')),
            workspace_epoch=int(payload.get('workspace_epoch', 1)),
            ui_attachable=bool(payload.get('ui_attachable', True)),
            last_started_at=clean_text(payload.get('last_started_at')),
            last_destroyed_at=clean_text(payload.get('last_destroyed_at')),
            last_destroy_reason=clean_text(payload.get('last_destroy_reason')),
            backend_family=clean_text(payload.get('backend_family')),
            backend_impl=clean_text(payload.get('backend_impl')),
        )

    def summary_fields(self) -> dict[str, object]:
        return {
            'namespace_epoch': self.namespace_epoch,
            'namespace_backend_ref': self.tmux_socket_path,
            'namespace_session_name': self.tmux_session_name,
            'namespace_tmux_socket_path': self.tmux_socket_path,
            'namespace_tmux_session_name': self.tmux_session_name,
            'namespace_layout_version': self.layout_version,
            'namespace_control_window_name': self.control_window_name,
            'namespace_control_window_id': self.control_window_id,
            'namespace_workspace_name': self.workspace_window_name,
            'namespace_workspace_window_name': self.workspace_window_name,
            'namespace_workspace_window_id': self.workspace_window_id,
            'namespace_workspace_epoch': self.workspace_epoch,
            'namespace_ui_attachable': self.ui_attachable,
            'namespace_last_started_at': self.last_started_at,
            'namespace_last_destroyed_at': self.last_destroyed_at,
            'namespace_last_destroy_reason': self.last_destroy_reason,
            'namespace_backend_family': self.backend_family,
            'namespace_backend_impl': self.backend_impl,
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

    @property
    def backend_ref(self) -> str | None:
        return self.tmux_socket_path

    @property
    def session_name(self) -> str | None:
        return self.tmux_session_name

    def __post_init__(self) -> None:
        require_non_empty_text(self.event_kind, field_name='event_kind')
        require_non_empty_text(self.project_id, field_name='project_id')
        require_non_empty_text(self.occurred_at, field_name='occurred_at')
        if self.namespace_epoch is not None:
            require_positive_int(self.namespace_epoch, field_name='namespace_epoch')

    def to_record(self) -> dict[str, Any]:
        return {
            'schema_version': SCHEMA_VERSION,
            'record_type': NAMESPACE_EVENT_RECORD_TYPE,
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
        require_schema_version(payload)
        require_record_type(payload, record_type=NAMESPACE_EVENT_RECORD_TYPE)
        details = record_details(payload)
        epoch = payload.get('namespace_epoch')
        return cls(
            event_kind=str(payload['event_kind']),
            project_id=str(payload['project_id']),
            occurred_at=str(payload['occurred_at']),
            namespace_epoch=int(epoch) if epoch is not None else None,
            tmux_socket_path=clean_text(payload.get('tmux_socket_path')),
            tmux_session_name=clean_text(payload.get('tmux_session_name')),
            details=details,
        )

    def summary_fields(self) -> dict[str, object]:
        return {
            'namespace_last_event_kind': self.event_kind,
            'namespace_last_event_at': self.occurred_at,
            'namespace_last_event_epoch': self.namespace_epoch,
            'namespace_last_event_backend_ref': self.tmux_socket_path,
            'namespace_last_event_socket_path': self.tmux_socket_path,
            'namespace_last_event_session_name': self.tmux_session_name,
        }


def require_non_empty_text(value: object, *, field_name: str) -> None:
    if not str(value or '').strip():
        raise ValueError(f'{field_name} cannot be empty')


def require_positive_int(value: int, *, field_name: str) -> None:
    if int(value) <= 0:
        raise ValueError(f'{field_name} must be positive')


def record_details(payload: dict[str, Any]) -> dict[str, object]:
    details = payload.get('details') or {}
    if not isinstance(details, dict):
        raise ValueError('details must be an object')
    return dict(details)


__all__ = ['ProjectNamespaceEvent', 'ProjectNamespaceState']
