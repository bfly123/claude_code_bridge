from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from ccbd.models import CcbdLease, LeaseHealth, LeaseInspection, MountState
from ccbd.system import parse_utc_timestamp, process_exists, unix_socket_connectable, utc_now
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
        socket_probe=unix_socket_connectable,
        heartbeat_grace_seconds: float = 15.0,
    ) -> None:
        self._layout = layout
        self._mount_manager = mount_manager
        self._clock = clock
        self._pid_exists = pid_exists
        self._socket_probe = socket_probe
        self._heartbeat_grace_seconds = heartbeat_grace_seconds

    @contextmanager
    def startup_lock(self):
        lock_path = self._layout.ccbd_dir / 'startup.lock'
        with file_lock(lock_path):
            yield

    def inspect(self, lease: CcbdLease | None = None) -> LeaseInspection:
        current = lease if lease is not None else self._mount_manager.load_state()
        if current is None:
            return LeaseInspection(
                lease=None,
                health=LeaseHealth.MISSING,
                pid_alive=False,
                socket_connectable=False,
                heartbeat_fresh=False,
                takeover_allowed=True,
                reason='lease_missing',
            )

        pid_alive = self._pid_exists(current.ccbd_pid)
        heartbeat_fresh = self._heartbeat_is_fresh(current)
        socket_connectable = False
        if current.mount_state is MountState.MOUNTED:
            socket_connectable = self._socket_probe(current.socket_path)

        if current.mount_state is MountState.UNMOUNTED:
            return LeaseInspection(
                lease=current,
                health=LeaseHealth.UNMOUNTED,
                pid_alive=pid_alive,
                socket_connectable=socket_connectable,
                heartbeat_fresh=heartbeat_fresh,
                takeover_allowed=True,
                reason='lease_unmounted',
            )

        if pid_alive and heartbeat_fresh and socket_connectable:
            return LeaseInspection(
                lease=current,
                health=LeaseHealth.HEALTHY,
                pid_alive=True,
                socket_connectable=True,
                heartbeat_fresh=True,
                takeover_allowed=False,
                reason='healthy',
            )

        takeover_allowed = (not pid_alive) or (pid_alive and not heartbeat_fresh and not socket_connectable)
        health = LeaseHealth.STALE if takeover_allowed else LeaseHealth.DEGRADED
        reason_parts: list[str] = []
        if not pid_alive:
            reason_parts.append('pid_missing')
        if not heartbeat_fresh:
            reason_parts.append('heartbeat_stale')
        if not socket_connectable:
            reason_parts.append('socket_unreachable')
        return LeaseInspection(
            lease=current,
            health=health,
            pid_alive=pid_alive,
            socket_connectable=socket_connectable,
            heartbeat_fresh=heartbeat_fresh,
            takeover_allowed=takeover_allowed,
            reason=','.join(reason_parts) or health.value,
        )

    def verify_or_takeover(self, *, project_id: str, pid: int, socket_path: str | Path) -> int:
        current = self._mount_manager.load_state()
        if current is None:
            return 1
        if current.project_id != project_id:
            raise OwnershipConflictError(
                f'lease project_id mismatch: expected {project_id}, found {current.project_id}'
            )
        current_socket = str(Path(current.socket_path))
        desired_socket = str(Path(socket_path))
        if current.ccbd_pid == pid and current_socket == desired_socket:
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


__all__ = ['OwnershipConflictError', 'OwnershipGuard']
