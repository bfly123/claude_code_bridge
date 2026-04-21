from __future__ import annotations

from pathlib import Path

from ccbd.models import CcbdLease, MountState, SCHEMA_VERSION
from ccbd.system import current_uid, read_boot_id, utc_now
from storage.json_store import JsonStore
from storage.paths import PathLayout


class MountManager:
    def __init__(
        self,
        layout: PathLayout,
        store: JsonStore | None = None,
        *,
        clock=utc_now,
        uid_getter=current_uid,
        boot_id_getter=read_boot_id,
    ) -> None:
        self._layout = layout
        self._store = store or JsonStore()
        self._clock = clock
        self._uid_getter = uid_getter
        self._boot_id_getter = boot_id_getter

    def load_state(self) -> CcbdLease | None:
        path = self._layout.ccbd_lease_path
        if not path.exists():
            return None
        return self._store.load(path, loader=_lease_from_record)

    def mark_mounted(
        self,
        *,
        project_id: str,
        pid: int,
        socket_path: str | Path,
        generation: int,
        started_at: str | None = None,
        config_signature: str | None = None,
        keeper_pid: int | None = None,
        daemon_instance_id: str | None = None,
    ) -> CcbdLease:
        timestamp = started_at or self._clock()
        lease = CcbdLease(
            project_id=project_id,
            ccbd_pid=pid,
            socket_path=str(socket_path),
            owner_uid=self._uid_getter(),
            boot_id=self._boot_id_getter(),
            started_at=timestamp,
            last_heartbeat_at=timestamp,
            mount_state=MountState.MOUNTED,
            generation=generation,
            config_signature=(str(config_signature).strip() or None) if config_signature is not None else None,
            keeper_pid=int(keeper_pid) if keeper_pid else None,
            daemon_instance_id=(str(daemon_instance_id).strip() or None) if daemon_instance_id is not None else None,
        )
        self._store.save(self._layout.ccbd_lease_path, lease, serializer=lambda value: value.to_record())
        return lease

    def refresh_heartbeat(self, *, expected_pid: int | None = None, expected_daemon_instance_id: str | None = None) -> CcbdLease:
        lease = self.load_state()
        if lease is None:
            raise RuntimeError('ccbd lease does not exist')
        if lease.mount_state is not MountState.MOUNTED:
            return lease
        self._assert_expected_holder(
            lease,
            expected_pid=expected_pid,
            expected_daemon_instance_id=expected_daemon_instance_id,
        )
        updated = lease.with_heartbeat(self._clock())
        self._store.save(self._layout.ccbd_lease_path, updated, serializer=lambda value: value.to_record())
        return updated

    def mark_unmounted(
        self,
        *,
        expected_pid: int | None = None,
        expected_daemon_instance_id: str | None = None,
    ) -> CcbdLease | None:
        lease = self.load_state()
        if lease is None:
            return None
        self._assert_expected_holder(
            lease,
            expected_pid=expected_pid,
            expected_daemon_instance_id=expected_daemon_instance_id,
        )
        updated = lease.with_mount_state(MountState.UNMOUNTED, heartbeat_at=self._clock())
        self._store.save(self._layout.ccbd_lease_path, updated, serializer=lambda value: value.to_record())
        return updated

    def _assert_expected_holder(
        self,
        lease: CcbdLease,
        *,
        expected_pid: int | None,
        expected_daemon_instance_id: str | None,
    ) -> None:
        if expected_pid is not None and int(lease.ccbd_pid) != int(expected_pid):
            raise RuntimeError(
                f'ccbd lease holder changed: expected pid={expected_pid}, found pid={lease.ccbd_pid}'
            )
        expected_instance = str(expected_daemon_instance_id or '').strip()
        if expected_instance:
            current_instance = str(lease.daemon_instance_id or '').strip()
            if current_instance != expected_instance:
                raise RuntimeError(
                    'ccbd lease holder changed: '
                    f'expected daemon_instance_id={expected_instance}, found daemon_instance_id={current_instance or "<missing>"}'
                )


def _lease_from_record(record: dict) -> CcbdLease:
    if record.get('schema_version') != SCHEMA_VERSION:
        raise ValueError(f'schema_version must be {SCHEMA_VERSION}')
    if record.get('record_type') != 'ccbd_lease':
        raise ValueError("record_type must be 'ccbd_lease'")
    return CcbdLease(
        project_id=record['project_id'],
        ccbd_pid=int(record['ccbd_pid']),
        socket_path=record['socket_path'],
        owner_uid=int(record['owner_uid']),
        boot_id=record['boot_id'],
        started_at=record['started_at'],
        last_heartbeat_at=record['last_heartbeat_at'],
        mount_state=MountState(record['mount_state']),
        generation=int(record.get('generation', 1)),
        config_signature=str(record.get('config_signature') or '').strip() or None,
        keeper_pid=int(record['keeper_pid']) if record.get('keeper_pid') else None,
        daemon_instance_id=str(record.get('daemon_instance_id') or '').strip() or None,
        api_version=int(record.get('api_version', 2)),
    )


__all__ = ['MountManager']
