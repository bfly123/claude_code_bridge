from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import os

from ccbd.models import CcbdLease, LeaseHealth, LeaseInspection, MountState
from ccbd.system import ipc_endpoint_connectable, parse_utc_timestamp, process_exists, utc_now
from storage.locks import file_lock
from storage.paths import PathLayout


class OwnershipConflictError(RuntimeError):
    pass


class OwnershipGuard:
    def __init__(
        self,
        layout: PathLayout,
        mount_manager,
        *,
        clock=utc_now,
        pid_exists=process_exists,
        socket_probe=ipc_endpoint_connectable,
        heartbeat_grace_seconds: float = 15.0,
        current_pid: int | None = None,
    ) -> None:
        self._layout = layout
        self._mount_manager = mount_manager
        self._clock = clock
        self._pid_exists = pid_exists
        self._socket_probe = socket_probe
        self._heartbeat_grace_seconds = heartbeat_grace_seconds
        self._current_pid = os.getpid() if current_pid is None else int(current_pid)

    @contextmanager
    def startup_lock(self):
        lock_path = self._layout.ccbd_dir / 'startup.lock'
        with file_lock(lock_path):
            yield

    def inspect(self, lease: CcbdLease | None = None) -> LeaseInspection:
        current = lease if lease is not None else self._mount_manager.load_state()
        if current is None:
            return self._missing_inspection()

        pid_alive, heartbeat_fresh, socket_connectable = self._lease_signals(current)
        if current.mount_state is MountState.UNMOUNTED:
            return self._inspection(
                current,
                health=LeaseHealth.UNMOUNTED,
                pid_alive=pid_alive,
                socket_connectable=socket_connectable,
                heartbeat_fresh=heartbeat_fresh,
                takeover_allowed=True,
                reason='lease_unmounted',
            )
        if pid_alive and heartbeat_fresh and socket_connectable:
            return self._inspection(
                current,
                health=LeaseHealth.HEALTHY,
                pid_alive=True,
                socket_connectable=True,
                heartbeat_fresh=True,
                takeover_allowed=False,
                reason='healthy',
            )

        takeover_allowed = self._takeover_allowed(
            pid_alive=pid_alive,
            heartbeat_fresh=heartbeat_fresh,
            socket_connectable=socket_connectable,
        )
        health = LeaseHealth.STALE if takeover_allowed else LeaseHealth.DEGRADED
        return self._inspection(
            current,
            health=health,
            pid_alive=pid_alive,
            socket_connectable=socket_connectable,
            heartbeat_fresh=heartbeat_fresh,
            takeover_allowed=takeover_allowed,
            reason=self._inspection_reason(
                health=health,
                pid_alive=pid_alive,
                heartbeat_fresh=heartbeat_fresh,
                socket_connectable=socket_connectable,
            ),
        )

    def verify_or_takeover(self, *, project_id: str, pid: int, socket_path: str | Path) -> int:
        current = self._mount_manager.load_state()
        if current is None:
            return 1
        self._assert_project_id(current, project_id=project_id)
        if self._same_holder(current, pid=pid, socket_path=socket_path):
            return current.generation
        inspection = self.inspect(current)
        if inspection.takeover_allowed:
            return current.generation + 1
        raise OwnershipConflictError(
            f'ccbd lease is held by pid={current.ccbd_pid} generation={current.generation}: {inspection.reason}'
        )

    def _heartbeat_is_fresh(self, lease: CcbdLease) -> bool:
        try:
            current = parse_utc_timestamp(self._clock())
            heartbeat = parse_utc_timestamp(lease.last_heartbeat_at)
        except Exception:
            return False
        delta = (current - heartbeat).total_seconds()
        return delta <= self._heartbeat_grace_seconds

    def _missing_inspection(self) -> LeaseInspection:
        return LeaseInspection(
            lease=None,
            health=LeaseHealth.MISSING,
            pid_alive=False,
            socket_connectable=False,
            heartbeat_fresh=False,
            takeover_allowed=True,
            reason='lease_missing',
        )

    def _lease_signals(self, lease: CcbdLease) -> tuple[bool, bool, bool]:
        pid_alive = self._pid_exists(lease.ccbd_pid)
        heartbeat_fresh = self._heartbeat_is_fresh(lease)
        socket_connectable = self._mounted_socket_connectable(lease)
        return pid_alive, heartbeat_fresh, socket_connectable

    def _mounted_socket_connectable(self, lease: CcbdLease) -> bool:
        if lease.mount_state is not MountState.MOUNTED:
            return False
        if lease.ccbd_pid == self._current_pid:
            return True
        ipc_kind = getattr(lease, 'ipc_kind', None)
        try:
            return self._socket_probe(lease.socket_path, ipc_kind=ipc_kind)
        except TypeError:
            return self._socket_probe(lease.socket_path)

    def _takeover_allowed(
        self,
        *,
        pid_alive: bool,
        heartbeat_fresh: bool,
        socket_connectable: bool,
    ) -> bool:
        return (not pid_alive) or (pid_alive and not heartbeat_fresh and not socket_connectable)

    def _inspection_reason(
        self,
        *,
        health: LeaseHealth,
        pid_alive: bool,
        heartbeat_fresh: bool,
        socket_connectable: bool,
    ) -> str:
        reason_parts: list[str] = []
        if not pid_alive:
            reason_parts.append('pid_missing')
        if not heartbeat_fresh:
            reason_parts.append('heartbeat_stale')
        if not socket_connectable:
            reason_parts.append('socket_unreachable')
        return ','.join(reason_parts) or health.value

    def _inspection(
        self,
        lease: CcbdLease | None,
        *,
        health: LeaseHealth,
        pid_alive: bool,
        socket_connectable: bool,
        heartbeat_fresh: bool,
        takeover_allowed: bool,
        reason: str,
    ) -> LeaseInspection:
        return LeaseInspection(
            lease=lease,
            health=health,
            pid_alive=pid_alive,
            socket_connectable=socket_connectable,
            heartbeat_fresh=heartbeat_fresh,
            takeover_allowed=takeover_allowed,
            reason=reason,
        )

    def _assert_project_id(self, lease: CcbdLease, *, project_id: str) -> None:
        if lease.project_id == project_id:
            return
        raise OwnershipConflictError(
            f'lease project_id mismatch: expected {project_id}, found {lease.project_id}'
        )

    def _same_holder(self, lease: CcbdLease, *, pid: int, socket_path: str | Path) -> bool:
        current_socket = str(lease.socket_path)
        desired_socket = str(socket_path)
        return lease.ccbd_pid == pid and current_socket == desired_socket


__all__ = ['OwnershipConflictError', 'OwnershipGuard']
