from __future__ import annotations

from pathlib import Path

from ccbd.system import parse_utc_timestamp, process_exists

from .records import KeeperState


_MAX_KEEPER_RESTARTS = 5


def restart_backoff_active(*, state: KeeperState, now: str) -> bool:
    if state.restart_count <= 0 or state.last_failure_reason is None or state.last_restart_at is None:
        return False
    try:
        elapsed = (parse_utc_timestamp(now) - parse_utc_timestamp(state.last_restart_at)).total_seconds()
    except Exception:
        return False
    return elapsed < restart_backoff_seconds(state.restart_count)


def restart_backoff_seconds(restart_count: int) -> float:
    capped = min(max(1, int(restart_count)), 5)
    return min(8.0, 0.5 * float(2 ** (capped - 1)))


def restart_limit_reached(*, state: KeeperState) -> bool:
    return bool(state.last_failure_reason) and int(state.restart_count or 0) >= _MAX_KEEPER_RESTARTS


def compute_project_id(project_root: Path) -> str:
    from project.ids import compute_project_id as _compute_project_id

    return _compute_project_id(project_root)


def keeper_state_is_running(state: KeeperState | None, *, process_exists_fn=process_exists) -> bool:
    if state is None:
        return False
    if state.state != 'running':
        return False
    return process_exists_fn(state.keeper_pid)


__all__ = [
    'compute_project_id',
    'keeper_state_is_running',
    'restart_backoff_active',
    'restart_backoff_seconds',
    'restart_limit_reached',
]
