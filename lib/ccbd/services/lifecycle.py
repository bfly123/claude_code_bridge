from __future__ import annotations

from dataclasses import dataclass, replace
import os
from pathlib import Path
from typing import Any

from ccbd.models import MountState, SCHEMA_VERSION
from storage.json_store import JsonStore
from storage.paths import PathLayout


_RECORD_TYPE = 'ccbd_lifecycle'
_DESIRED_STATES = {'running', 'stopped'}
_PHASES = {'unmounted', 'starting', 'mounted', 'stopping', 'failed'}


def _clean_text(value: object) -> str | None:
    text = str(value or '').strip()
    return text or None


def _clean_positive_int(value: object) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    number = int(text)
    if number <= 0:
        raise ValueError(f'expected positive integer, got {value!r}')
    return number


@dataclass(frozen=True)
class CcbdLifecycle:
    project_id: str
    desired_state: str
    phase: str
    generation: int
    phase_started_at: str
    startup_id: str | None = None
    keeper_pid: int | None = None
    owner_pid: int | None = None
    owner_daemon_instance_id: str | None = None
    config_signature: str | None = None
    socket_path: str | None = None
    socket_inode: int | None = None
    namespace_epoch: int | None = None
    last_failure_reason: str | None = None
    shutdown_intent: str | None = None

    def __post_init__(self) -> None:
        if not str(self.project_id or '').strip():
            raise ValueError('project_id cannot be empty')
        if self.desired_state not in _DESIRED_STATES:
            raise ValueError(f'invalid desired_state: {self.desired_state!r}')
        if self.phase not in _PHASES:
            raise ValueError(f'invalid phase: {self.phase!r}')
        if int(self.generation) < 0:
            raise ValueError('generation cannot be negative')
        if not str(self.phase_started_at or '').strip():
            raise ValueError('phase_started_at cannot be empty')
        if self.keeper_pid is not None and int(self.keeper_pid) <= 0:
            raise ValueError('keeper_pid must be positive')
        if self.owner_pid is not None and int(self.owner_pid) <= 0:
            raise ValueError('owner_pid must be positive')
        if self.socket_inode is not None and int(self.socket_inode) <= 0:
            raise ValueError('socket_inode must be positive')
        if self.namespace_epoch is not None and int(self.namespace_epoch) < 0:
            raise ValueError('namespace_epoch cannot be negative')

    def with_updates(self, **kwargs) -> CcbdLifecycle:
        return replace(self, **kwargs)

    def with_phase(self, phase: str, *, occurred_at: str, **kwargs) -> CcbdLifecycle:
        return replace(self, phase=phase, phase_started_at=occurred_at, **kwargs)

    def to_record(self) -> dict[str, Any]:
        return {
            'schema_version': SCHEMA_VERSION,
            'record_type': _RECORD_TYPE,
            'project_id': self.project_id,
            'desired_state': self.desired_state,
            'phase': self.phase,
            'generation': self.generation,
            'phase_started_at': self.phase_started_at,
            'startup_id': self.startup_id,
            'keeper_pid': self.keeper_pid,
            'owner_pid': self.owner_pid,
            'owner_daemon_instance_id': self.owner_daemon_instance_id,
            'config_signature': self.config_signature,
            'socket_path': self.socket_path,
            'socket_inode': self.socket_inode,
            'namespace_epoch': self.namespace_epoch,
            'last_failure_reason': self.last_failure_reason,
            'shutdown_intent': self.shutdown_intent,
        }

    @classmethod
    def from_record(cls, payload: dict[str, Any]) -> CcbdLifecycle:
        if payload.get('schema_version') != SCHEMA_VERSION:
            raise ValueError(f'schema_version must be {SCHEMA_VERSION}')
        if payload.get('record_type') != _RECORD_TYPE:
            raise ValueError(f"record_type must be '{_RECORD_TYPE}'")
        return cls(
            project_id=str(payload['project_id']),
            desired_state=str(payload['desired_state']),
            phase=str(payload['phase']),
            generation=int(payload.get('generation', 0)),
            phase_started_at=str(payload['phase_started_at']),
            startup_id=_clean_text(payload.get('startup_id')),
            keeper_pid=_clean_positive_int(payload.get('keeper_pid')),
            owner_pid=_clean_positive_int(payload.get('owner_pid')),
            owner_daemon_instance_id=_clean_text(payload.get('owner_daemon_instance_id')),
            config_signature=_clean_text(payload.get('config_signature')),
            socket_path=_clean_text(payload.get('socket_path')),
            socket_inode=_clean_positive_int(payload.get('socket_inode')),
            namespace_epoch=int(payload['namespace_epoch']) if payload.get('namespace_epoch') is not None else None,
            last_failure_reason=_clean_text(payload.get('last_failure_reason')),
            shutdown_intent=_clean_text(payload.get('shutdown_intent')),
        )


class CcbdLifecycleStore:
    def __init__(self, layout: PathLayout, store: JsonStore | None = None) -> None:
        self._layout = layout
        self._store = store or JsonStore()

    def load(self) -> CcbdLifecycle | None:
        path = self._layout.ccbd_lifecycle_path
        if not path.exists():
            return None
        return self._store.load(path, loader=CcbdLifecycle.from_record)

    def save(self, lifecycle: CcbdLifecycle) -> None:
        self._store.save(self._layout.ccbd_lifecycle_path, lifecycle, serializer=lambda value: value.to_record())


def build_lifecycle(
    *,
    project_id: str,
    occurred_at: str,
    desired_state: str,
    phase: str,
    generation: int,
    startup_id: str | None = None,
    keeper_pid: int | None = None,
    owner_pid: int | None = None,
    owner_daemon_instance_id: str | None = None,
    config_signature: str | None = None,
    socket_path: str | Path | None = None,
    socket_inode: int | None = None,
    namespace_epoch: int | None = None,
    last_failure_reason: str | None = None,
    shutdown_intent: str | None = None,
) -> CcbdLifecycle:
    return CcbdLifecycle(
        project_id=project_id,
        desired_state=desired_state,
        phase=phase,
        generation=int(generation),
        phase_started_at=str(occurred_at),
        startup_id=_clean_text(startup_id),
        keeper_pid=_clean_positive_int(keeper_pid),
        owner_pid=_clean_positive_int(owner_pid),
        owner_daemon_instance_id=_clean_text(owner_daemon_instance_id),
        config_signature=_clean_text(config_signature),
        socket_path=str(Path(socket_path)) if socket_path else None,
        socket_inode=_clean_positive_int(socket_inode),
        namespace_epoch=int(namespace_epoch) if namespace_epoch is not None else None,
        last_failure_reason=_clean_text(last_failure_reason),
        shutdown_intent=_clean_text(shutdown_intent),
    )


def lifecycle_from_inspection(
    *,
    project_id: str,
    inspection,
    occurred_at: str,
    config_signature: str | None = None,
    keeper_pid: int | None = None,
) -> CcbdLifecycle:
    lease = getattr(inspection, 'lease', None)
    if lease is None:
        return build_lifecycle(
            project_id=project_id,
            occurred_at=occurred_at,
            desired_state='stopped',
            phase='unmounted',
            generation=0,
            keeper_pid=keeper_pid,
            config_signature=config_signature,
        )
    generation = int(getattr(lease, 'generation', 0) or 0)
    owner_pid = int(getattr(lease, 'ccbd_pid', 0) or 0) or None
    socket_path = str(getattr(lease, 'socket_path', '') or '').strip() or None
    desired_state = 'stopped'
    phase = 'unmounted'
    socket_inode = None
    if getattr(lease, 'mount_state', None) is not MountState.UNMOUNTED:
        desired_state = 'running'
        phase = 'mounted' if bool(getattr(inspection, 'socket_connectable', False)) else 'failed'
        socket_inode = current_socket_inode(socket_path)
    return build_lifecycle(
        project_id=project_id,
        occurred_at=occurred_at,
        desired_state=desired_state,
        phase=phase,
        generation=generation,
        keeper_pid=keeper_pid or _clean_positive_int(getattr(lease, 'keeper_pid', None)),
        owner_pid=owner_pid,
        owner_daemon_instance_id=_clean_text(getattr(lease, 'daemon_instance_id', None)),
        config_signature=_clean_text(getattr(lease, 'config_signature', None)) or config_signature,
        socket_path=socket_path,
        socket_inode=socket_inode,
    )


def current_socket_inode(path: str | Path | None) -> int | None:
    if not path:
        return None
    try:
        stat = os.stat(Path(path))
    except OSError:
        return None
    inode = int(getattr(stat, 'st_ino', 0) or 0)
    return inode if inode > 0 else None


__all__ = [
    'CcbdLifecycle',
    'CcbdLifecycleStore',
    'build_lifecycle',
    'current_socket_inode',
    'lifecycle_from_inspection',
]
