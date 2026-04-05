from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import errno
import os
import time
from typing import Any

from agents.config_identity import project_config_identity_payload
from agents.config_loader import load_project_config
from ccbd.daemon_process import CcbdProcessError, spawn_ccbd_process
from ccbd.models import LeaseHealth, SCHEMA_VERSION
from ccbd.services.mount import MountManager
from ccbd.services.ownership import OwnershipGuard
from ccbd.socket_client import CcbdClient, CcbdClientError
from ccbd.system import parse_utc_timestamp, process_exists, utc_now
from cli.kill_runtime.processes import terminate_pid_tree
from storage.json_store import JsonStore
from storage.paths import PathLayout


_KEEPER_RECORD_TYPE = 'ccbd_keeper'
_SHUTDOWN_INTENT_RECORD_TYPE = 'ccbd_shutdown_intent'


@dataclass(frozen=True)
class KeeperState:
    project_id: str
    keeper_pid: int
    started_at: str
    last_check_at: str
    state: str
    restart_count: int = 0
    last_restart_at: str | None = None
    last_failure_reason: str | None = None

    def __post_init__(self) -> None:
        if self.keeper_pid <= 0:
            raise ValueError('keeper_pid must be positive')
        if not str(self.project_id or '').strip():
            raise ValueError('project_id cannot be empty')
        if not str(self.started_at or '').strip():
            raise ValueError('started_at cannot be empty')
        if not str(self.last_check_at or '').strip():
            raise ValueError('last_check_at cannot be empty')
        if not str(self.state or '').strip():
            raise ValueError('state cannot be empty')
        if self.restart_count < 0:
            raise ValueError('restart_count cannot be negative')

    def with_check(self, occurred_at: str) -> KeeperState:
        return replace(self, last_check_at=occurred_at)

    def with_state(self, state: str, *, occurred_at: str) -> KeeperState:
        return replace(self, state=state, last_check_at=occurred_at)

    def with_restart_attempt(self, *, occurred_at: str) -> KeeperState:
        return replace(
            self,
            last_check_at=occurred_at,
            restart_count=self.restart_count + 1,
            last_restart_at=occurred_at,
        )

    def with_failure(self, *, occurred_at: str, reason: str) -> KeeperState:
        return replace(
            self,
            last_check_at=occurred_at,
            last_failure_reason=str(reason or '').strip() or 'unknown_failure',
        )

    def with_success(self, *, occurred_at: str) -> KeeperState:
        return replace(
            self,
            last_check_at=occurred_at,
            last_failure_reason=None,
        )

    def to_record(self) -> dict[str, Any]:
        return {
            'schema_version': SCHEMA_VERSION,
            'record_type': _KEEPER_RECORD_TYPE,
            'project_id': self.project_id,
            'keeper_pid': self.keeper_pid,
            'started_at': self.started_at,
            'last_check_at': self.last_check_at,
            'state': self.state,
            'restart_count': self.restart_count,
            'last_restart_at': self.last_restart_at,
            'last_failure_reason': self.last_failure_reason,
        }

    @classmethod
    def from_record(cls, payload: dict[str, Any]) -> KeeperState:
        if payload.get('schema_version') != SCHEMA_VERSION:
            raise ValueError(f'schema_version must be {SCHEMA_VERSION}')
        if payload.get('record_type') != _KEEPER_RECORD_TYPE:
            raise ValueError(f"record_type must be '{_KEEPER_RECORD_TYPE}'")
        return cls(
            project_id=str(payload['project_id']),
            keeper_pid=int(payload['keeper_pid']),
            started_at=str(payload['started_at']),
            last_check_at=str(payload['last_check_at']),
            state=str(payload['state']),
            restart_count=int(payload.get('restart_count', 0)),
            last_restart_at=str(payload.get('last_restart_at') or '').strip() or None,
            last_failure_reason=str(payload.get('last_failure_reason') or '').strip() or None,
        )


@dataclass(frozen=True)
class ShutdownIntent:
    project_id: str
    requested_at: str
    requested_by_pid: int
    reason: str

    def __post_init__(self) -> None:
        if not str(self.project_id or '').strip():
            raise ValueError('project_id cannot be empty')
        if not str(self.requested_at or '').strip():
            raise ValueError('requested_at cannot be empty')
        if self.requested_by_pid <= 0:
            raise ValueError('requested_by_pid must be positive')
        if not str(self.reason or '').strip():
            raise ValueError('reason cannot be empty')

    def to_record(self) -> dict[str, Any]:
        return {
            'schema_version': SCHEMA_VERSION,
            'record_type': _SHUTDOWN_INTENT_RECORD_TYPE,
            'project_id': self.project_id,
            'requested_at': self.requested_at,
            'requested_by_pid': self.requested_by_pid,
            'reason': self.reason,
        }

    @classmethod
    def from_record(cls, payload: dict[str, Any]) -> ShutdownIntent:
        if payload.get('schema_version') != SCHEMA_VERSION:
            raise ValueError(f'schema_version must be {SCHEMA_VERSION}')
        if payload.get('record_type') != _SHUTDOWN_INTENT_RECORD_TYPE:
            raise ValueError(f"record_type must be '{_SHUTDOWN_INTENT_RECORD_TYPE}'")
        return cls(
            project_id=str(payload['project_id']),
            requested_at=str(payload['requested_at']),
            requested_by_pid=int(payload['requested_by_pid']),
            reason=str(payload['reason']),
        )


class KeeperStateStore:
    def __init__(self, layout: PathLayout, store: JsonStore | None = None) -> None:
        self._layout = layout
        self._store = store or JsonStore()

    def load(self) -> KeeperState | None:
        path = self._layout.ccbd_keeper_path
        if not path.exists():
            return None
        return self._store.load(path, loader=KeeperState.from_record)

    def save(self, state: KeeperState) -> None:
        self._store.save(self._layout.ccbd_keeper_path, state, serializer=lambda value: value.to_record())


class ShutdownIntentStore:
    def __init__(self, layout: PathLayout, store: JsonStore | None = None) -> None:
        self._layout = layout
        self._store = store or JsonStore()

    def load(self) -> ShutdownIntent | None:
        path = self._layout.ccbd_shutdown_intent_path
        if not path.exists():
            return None
        return self._store.load(path, loader=ShutdownIntent.from_record)

    def save(self, intent: ShutdownIntent) -> None:
        self._store.save(self._layout.ccbd_shutdown_intent_path, intent, serializer=lambda value: value.to_record())

    def clear(self) -> None:
        try:
            self._layout.ccbd_shutdown_intent_path.unlink()
        except FileNotFoundError:
            pass


class ProjectKeeper:
    def __init__(
        self,
        project_root: str | Path,
        *,
        clock=utc_now,
        pid: int | None = None,
        process_exists_fn=process_exists,
        sleep_fn=time.sleep,
        spawn_ccbd_process_fn=spawn_ccbd_process,
    ) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.paths = PathLayout(self.project_root)
        self.clock = clock
        self.pid = pid or os.getpid()
        self._sleep = sleep_fn
        self._spawn_ccbd_process = spawn_ccbd_process_fn
        self._process_exists = process_exists_fn
        self._mount_manager = MountManager(self.paths, clock=self.clock)
        self._ownership_guard = OwnershipGuard(self.paths, self._mount_manager, clock=self.clock)
        self._state_store = KeeperStateStore(self.paths)
        self._intent_store = ShutdownIntentStore(self.paths)

    def run_forever(self, *, poll_interval: float = 0.5, start_timeout_s: float = 5.0) -> int:
        lock_path = self.paths.ccbd_dir / 'keeper.lock'
        lock_handle = _try_acquire_keeper_lock(lock_path)
        if lock_handle is None:
            return 0
        cleanup_transient_keeper_files = False
        now = self.clock()
        state = KeeperState(
            project_id=_compute_project_id(self.project_root),
            keeper_pid=self.pid,
            started_at=now,
            last_check_at=now,
            state='running',
        )
        self._state_store.save(state)
        try:
            while True:
                _reap_child_processes()
                now = self.clock()
                if self._project_definition_missing():
                    cleanup_transient_keeper_files = True
                    return 0
                current_intent = self._intent_store.load()
                if current_intent is not None and current_intent.project_id == state.project_id:
                    self._state_store.save(state.with_state('stopped', occurred_at=now))
                    return 0
                state = self._reconcile_once(state=state.with_check(now), start_timeout_s=start_timeout_s)
                self._state_store.save(state)
                self._sleep(max(0.05, float(poll_interval)))
        finally:
            try:
                lock_handle.close()
            except Exception:
                pass
            if cleanup_transient_keeper_files:
                self._cleanup_transient_keeper_files(lock_path=lock_path)

    def _reconcile_once(self, *, state: KeeperState, start_timeout_s: float) -> KeeperState:
        now = self.clock()
        if _restart_backoff_active(state=state, now=now):
            return state

        inspection = self._ownership_guard.inspect()
        if inspection.socket_connectable:
            try:
                if self._daemon_matches_project_config():
                    return state.with_success(occurred_at=now)
                self._request_shutdown()
                return state.with_restart_attempt(occurred_at=now)
            except Exception as exc:
                return state.with_failure(occurred_at=now, reason=f'config_check_failed:{exc}')

        if inspection.health is LeaseHealth.DEGRADED and inspection.pid_alive and inspection.lease is not None:
            pid = int(inspection.lease.ccbd_pid or 0)
            if pid > 0:
                terminate_pid_tree(pid, timeout_s=1.0, is_pid_alive_fn=self._process_exists)
            return self._spawn_daemon(state=state.with_restart_attempt(occurred_at=now), start_timeout_s=start_timeout_s)

        if inspection.health in {LeaseHealth.MISSING, LeaseHealth.UNMOUNTED, LeaseHealth.STALE}:
            return self._spawn_daemon(state=state.with_restart_attempt(occurred_at=now), start_timeout_s=start_timeout_s)

        return state

    def _spawn_daemon(self, *, state: KeeperState, start_timeout_s: float) -> KeeperState:
        now = self.clock()
        try:
            load_project_config(self.project_root)
            self._spawn_ccbd_process(
                project_root=self.project_root,
                socket_path=self.paths.ccbd_socket_path,
                ccbd_dir=self.paths.ccbd_dir,
                timeout_s=start_timeout_s,
                keeper_pid=self.pid,
            )
            return state.with_success(occurred_at=now)
        except Exception as exc:
            return state.with_failure(occurred_at=now, reason=str(exc))

    def _daemon_matches_project_config(self) -> bool:
        expected = project_config_identity_payload(load_project_config(self.project_root).config)
        payload = CcbdClient(self.paths.ccbd_socket_path, timeout_s=0.2).ping('ccbd')
        actual_signature = str(payload.get('config_signature') or '').strip()
        if actual_signature:
            return actual_signature == expected['config_signature']
        known_agents = payload.get('known_agents')
        if not isinstance(known_agents, list):
            return False
        actual_agents = tuple(str(item).strip().lower() for item in known_agents if str(item).strip())
        return actual_agents == tuple(expected['known_agents'])

    def _request_shutdown(self) -> None:
        client = CcbdClient(self.paths.ccbd_socket_path, timeout_s=0.2)
        try:
            client.shutdown()
        except CcbdClientError:
            inspection = self._ownership_guard.inspect()
            if inspection.lease is not None and inspection.pid_alive:
                terminate_pid_tree(
                    int(inspection.lease.ccbd_pid or 0),
                    timeout_s=1.0,
                    is_pid_alive_fn=self._process_exists,
                )

    def _project_definition_missing(self) -> bool:
        if not self.paths.ccb_dir.exists():
            return True
        if not self.paths.config_path.exists():
            return True
        return False

    def _cleanup_transient_keeper_files(self, *, lock_path: Path) -> None:
        for path in (
            self.paths.ccbd_keeper_path,
            self.paths.ccbd_dir / 'keeper.stdout.log',
            self.paths.ccbd_dir / 'keeper.stderr.log',
            Path(lock_path),
        ):
            try:
                path.unlink()
            except FileNotFoundError:
                continue
            except Exception:
                continue
        for path in (self.paths.ccbd_dir, self.paths.ccb_dir):
            try:
                path.rmdir()
            except OSError:
                continue


def _restart_backoff_active(*, state: KeeperState, now: str) -> bool:
    if state.restart_count <= 0 or state.last_failure_reason is None or state.last_restart_at is None:
        return False
    try:
        elapsed = (parse_utc_timestamp(now) - parse_utc_timestamp(state.last_restart_at)).total_seconds()
    except Exception:
        return False
    return elapsed < _restart_backoff_seconds(state.restart_count)


def _restart_backoff_seconds(restart_count: int) -> float:
    capped = min(max(1, int(restart_count)), 5)
    return min(8.0, 0.5 * float(2 ** (capped - 1)))


def _compute_project_id(project_root: Path) -> str:
    from project.ids import compute_project_id

    return compute_project_id(project_root)


def keeper_state_is_running(state: KeeperState | None, *, process_exists_fn=process_exists) -> bool:
    if state is None:
        return False
    if state.state != 'running':
        return False
    return process_exists_fn(state.keeper_pid)


def _try_acquire_keeper_lock(path: Path):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    handle = target.open('a+', encoding='utf-8')
    try:
        import fcntl  # type: ignore

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except ModuleNotFoundError:
        return handle
    except OSError as exc:
        handle.close()
        if exc.errno in {errno.EACCES, errno.EAGAIN}:
            return None
        raise
    return handle


def _reap_child_processes(*, waitpid_fn=os.waitpid) -> tuple[int, ...]:
    if os.name == 'nt' or not hasattr(os, 'WNOHANG'):
        return ()
    reaped: list[int] = []
    while True:
        try:
            pid, _status = waitpid_fn(-1, os.WNOHANG)
        except ChildProcessError:
            break
        except OSError as exc:
            if exc.errno in {errno.ECHILD, errno.EINTR}:
                break
            break
        if pid <= 0:
            break
        reaped.append(int(pid))
    return tuple(reaped)


__all__ = [
    'KeeperState',
    'KeeperStateStore',
    'ProjectKeeper',
    'ShutdownIntent',
    'ShutdownIntentStore',
    '_reap_child_processes',
    'keeper_state_is_running',
]
