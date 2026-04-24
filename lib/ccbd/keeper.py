from __future__ import annotations

from datetime import timedelta
from pathlib import Path
import os
import time
import uuid

from agents.config_identity import project_config_identity_payload
from agents.config_loader import load_project_config
from ccbd.daemon_process import spawn_ccbd_process
from ccbd.keeper_runtime.app_state import KeeperAppState, KeeperAppStateMixin
from ccbd.keeper_runtime import KeeperState, KeeperStateStore, ShutdownIntent, ShutdownIntentStore, keeper_state_is_running
from ccbd.keeper_runtime.loop import cleanup_transient_keeper_files, daemon_matches_project_config, reconcile_once, request_shutdown, run_forever
from ccbd.keeper_runtime.state import compute_project_id
from ccbd.keeper_runtime.support import reap_child_processes, try_acquire_keeper_lock
from ccbd.services.lifecycle import CcbdLifecycleStore, current_socket_inode, lifecycle_from_inspection
from ccbd.services.mount import MountManager
from ccbd.services.ownership import OwnershipGuard
from ccbd.socket_client import CcbdClient, CcbdClientError
from ccbd.startup_policy import STARTUP_TRANSACTION_TIMEOUT_S
from ccbd.system import parse_utc_timestamp, process_exists, utc_now
from cli.kill_runtime.processes import terminate_pid_tree
from storage.paths import PathLayout


class ProjectKeeper(KeeperAppStateMixin):
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
        resolved_project_root = Path(project_root).expanduser().resolve()
        paths = PathLayout(resolved_project_root)
        mount_manager = MountManager(paths, clock=clock)
        self._runtime_state = KeeperAppState(
            project_root=resolved_project_root,
            paths=paths,
            clock=clock,
            pid=pid or os.getpid(),
            sleep=sleep_fn,
            spawn_ccbd_process=spawn_ccbd_process_fn,
            process_exists=process_exists_fn,
            mount_manager=mount_manager,
            lifecycle_store=CcbdLifecycleStore(paths),
            ownership_guard=OwnershipGuard(paths, mount_manager, clock=clock),
            state_store=KeeperStateStore(paths),
            intent_store=ShutdownIntentStore(paths),
        )

    def run_forever(self, *, poll_interval: float = 0.5, start_timeout_s: float = STARTUP_TRANSACTION_TIMEOUT_S) -> int:
        return run_forever(self, poll_interval=poll_interval, start_timeout_s=start_timeout_s)

    def _reconcile_once(self, *, state: KeeperState, start_timeout_s: float) -> KeeperState:
        return reconcile_once(self, state=state, start_timeout_s=start_timeout_s)

    def _spawn_daemon(self, *, state: KeeperState, start_timeout_s: float) -> KeeperState:
        return _spawn_daemon(self, state=state, start_timeout_s=start_timeout_s)

    def _daemon_matches_project_config(self) -> bool:
        return daemon_matches_project_config(self)

    def _request_shutdown(self) -> None:
        request_shutdown(self)

    def _project_definition_missing(self) -> bool:
        return _project_definition_missing(self)

    def _cleanup_transient_keeper_files(self, *, lock_path: Path) -> None:
        cleanup_transient_keeper_files(self, lock_path=lock_path)

    def _terminate_pid_tree(self, pid: int, *, timeout_s: float) -> bool:
        return terminate_pid_tree(pid, timeout_s=timeout_s, is_pid_alive_fn=self._process_exists)


def _spawn_daemon(app: ProjectKeeper, *, state: KeeperState, start_timeout_s: float) -> KeeperState:
    now = app.clock()
    inspection = app._ownership_guard.inspect()
    lifecycle = app._lifecycle_store.load()
    if lifecycle is None:
        lifecycle = lifecycle_from_inspection(
            project_id=compute_project_id(app.project_root),
            inspection=inspection,
            occurred_at=now,
            keeper_pid=app.pid,
        )
    try:
        config = load_project_config(app.project_root).config
        config_signature = str(project_config_identity_payload(config)['config_signature'])
        startup_id = uuid.uuid4().hex
        deadline_at = _timestamp_plus_seconds(now, start_timeout_s)
        starting = lifecycle.with_phase(
            'starting',
            occurred_at=now,
            desired_state='running',
            generation=max(int(lifecycle.generation), int(getattr(getattr(inspection, 'lease', None), 'generation', 0) or 0)) + 1,
            startup_id=startup_id,
            startup_stage='spawn_requested',
            last_progress_at=now,
            startup_deadline_at=deadline_at,
            keeper_pid=app.pid,
            owner_pid=None,
            owner_daemon_instance_id=None,
            config_signature=config_signature,
            socket_path=str(app.paths.ccbd_socket_path),
            socket_inode=None,
            last_failure_reason=None,
            shutdown_intent=None,
        )
        app._lifecycle_store.save(starting)
        app._spawn_ccbd_process(
            project_root=app.project_root,
            socket_path=app.paths.ccbd_socket_path,
            ccbd_dir=app.paths.ccbd_dir,
            timeout_s=start_timeout_s,
            keeper_pid=app.pid,
        )
        lease = app._mount_manager.load_state()
        app._lifecycle_store.save(
            starting.with_phase(
                'mounted',
                occurred_at=app.clock(),
                generation=int(getattr(lease, 'generation', 0) or starting.generation),
                owner_pid=int(getattr(lease, 'ccbd_pid', 0) or 0) or None,
                owner_daemon_instance_id=str(getattr(lease, 'daemon_instance_id', '') or '').strip() or None,
                config_signature=str(getattr(lease, 'config_signature', '') or '').strip() or config_signature,
                socket_path=str(getattr(lease, 'socket_path', '') or app.paths.ccbd_socket_path),
                socket_inode=current_socket_inode(getattr(lease, 'socket_path', app.paths.ccbd_socket_path)),
                startup_stage='mounted',
                last_progress_at=app.clock(),
                startup_deadline_at=None,
                last_failure_reason=None,
                shutdown_intent=None,
            )
        )
        return state.with_success(occurred_at=now)
    except Exception as exc:
        if 'starting' in locals():
            app._lifecycle_store.save(
                starting.with_phase(
                    'failed',
                    occurred_at=app.clock(),
                    owner_pid=None,
                    owner_daemon_instance_id=None,
                    socket_inode=None,
                    startup_stage='spawn_failed',
                    last_progress_at=app.clock(),
                    startup_deadline_at=None,
                    last_failure_reason=str(exc),
                )
            )
        return state.with_failure(occurred_at=now, reason=str(exc))


def _project_definition_missing(app: ProjectKeeper) -> bool:
    if not app.paths.ccb_dir.exists():
        return True
    if not app.paths.config_path.exists():
        return True
    return False


def _try_acquire_keeper_lock(path: Path):
    return try_acquire_keeper_lock(path)


def _reap_child_processes(*, waitpid_fn=os.waitpid) -> tuple[int, ...]:
    return reap_child_processes(waitpid_fn=waitpid_fn)


def _timestamp_plus_seconds(value: str, seconds: float) -> str:
    return (parse_utc_timestamp(value) + timedelta(seconds=max(0.0, float(seconds)))).isoformat().replace('+00:00', 'Z')


__all__ = [
    'KeeperState',
    'KeeperStateStore',
    'ProjectKeeper',
    'ShutdownIntent',
    'ShutdownIntentStore',
    '_reap_child_processes',
    'keeper_state_is_running',
]
