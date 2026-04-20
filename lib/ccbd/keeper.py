from __future__ import annotations

from pathlib import Path
import os
import time

from agents.config_identity import project_config_identity_payload
from agents.config_loader import load_project_config
from ccbd.daemon_process import spawn_ccbd_process
from ccbd.keeper_runtime.app_state import KeeperAppState, KeeperAppStateMixin
from ccbd.keeper_runtime import KeeperState, KeeperStateStore, ShutdownIntent, ShutdownIntentStore, keeper_state_is_running
from ccbd.keeper_runtime.loop import cleanup_transient_keeper_files, daemon_matches_project_config, reconcile_once, request_shutdown, run_forever
from ccbd.keeper_runtime.state import compute_project_id
from ccbd.keeper_runtime.support import reap_child_processes, try_acquire_keeper_lock
from ccbd.services.mount import MountManager
from ccbd.services.ownership import OwnershipGuard
from ccbd.socket_client import CcbdClient, CcbdClientError
from ccbd.system import process_exists, utc_now
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
            ownership_guard=OwnershipGuard(paths, mount_manager, clock=clock),
            state_store=KeeperStateStore(paths),
            intent_store=ShutdownIntentStore(paths),
        )

    def run_forever(self, *, poll_interval: float = 0.5, start_timeout_s: float = 5.0) -> int:
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
    try:
        load_project_config(app.project_root)
        app._spawn_ccbd_process(
            project_root=app.project_root,
            socket_path=app.paths.ccbd_socket_path,
            ccbd_dir=app.paths.ccbd_dir,
            timeout_s=start_timeout_s,
            keeper_pid=app.pid,
        )
        return state.with_success(occurred_at=now)
    except Exception as exc:
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


__all__ = [
    'KeeperState',
    'KeeperStateStore',
    'ProjectKeeper',
    'ShutdownIntent',
    'ShutdownIntentStore',
    '_reap_child_processes',
    'keeper_state_is_running',
]
