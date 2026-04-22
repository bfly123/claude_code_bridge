from __future__ import annotations

import os
import signal
import time

from agents.models import AgentState

from .helper_manifest import clear_helper_manifest, load_helper_manifest

_ACTIVE_STATES = {
    AgentState.STARTING,
    AgentState.IDLE,
    AgentState.BUSY,
    AgentState.DEGRADED,
}


def cleanup_stale_runtime_helper(paths, runtime) -> bool:
    helper_path = paths.agent_helper_path(runtime.agent_name)
    manifest = _load_helper_manifest_best_effort(helper_path)
    if manifest is None:
        return False
    if _runtime_owns_helper(runtime, manifest):
        return False
    return terminate_helper_manifest_path(helper_path)


def terminate_helper_manifest_path(path) -> bool:
    manifest = _load_helper_manifest_best_effort(path)
    if manifest is None:
        return False
    if _terminate_helper_manifest(manifest):
        clear_helper_manifest(path)
        return True
    return False


def _runtime_owns_helper(runtime, manifest) -> bool:
    provider = str(getattr(runtime, 'provider', '') or '').strip().lower()
    if provider != 'codex':
        return False
    if getattr(runtime, 'state', None) not in _ACTIVE_STATES:
        return False
    runtime_root = str(getattr(runtime, 'runtime_root', '') or '').strip()
    if not runtime_root:
        return False
    current_generation = _canonical_runtime_generation(runtime)
    if current_generation <= 0:
        return False
    return (
        str(getattr(runtime, 'agent_name', '') or '').strip() == manifest.agent_name
        and current_generation == int(manifest.runtime_generation)
    )


def _terminate_helper_manifest(manifest) -> bool:
    pgid = int(getattr(manifest, 'pgid', 0) or 0)
    leader_pid = int(getattr(manifest, 'leader_pid', 0) or 0)
    if pgid > 1 and _kill_helper_group(pgid, signal.SIGTERM):
        if _wait_for_helper_exit(leader_pid, timeout_s=0.2):
            return True
        if _kill_helper_group(pgid, signal.SIGKILL):
            return _wait_for_helper_exit(leader_pid, timeout_s=0.2)
    if leader_pid > 0:
        return _terminate_pid_tree(leader_pid)
    return False


def _kill_helper_group(pgid: int, sig) -> bool:
    if os.name == 'nt':
        return False
    current_pgid = _safe_getpgrp()
    if pgid <= 1 or (current_pgid is not None and pgid == current_pgid):
        return False
    try:
        os.killpg(pgid, sig)
        return True
    except ProcessLookupError:
        return True
    except Exception:
        return False


def _wait_for_helper_exit(leader_pid: int, *, timeout_s: float) -> bool:
    if leader_pid <= 0:
        return True
    deadline = time.time() + max(0.0, float(timeout_s))
    while time.time() < deadline:
        if not _is_pid_alive(leader_pid):
            return True
        time.sleep(0.05)
    return not _is_pid_alive(leader_pid)


def _terminate_pid_tree(pid: int) -> bool:
    if pid <= 0:
        return False
    if not _is_pid_alive(pid):
        return True
    if _kill_helper_group(pid, signal.SIGTERM) and _wait_for_helper_exit(pid, timeout_s=0.2):
        return True
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.kill(pid, sig)
        except ProcessLookupError:
            return True
        except Exception:
            return False
        if _wait_for_helper_exit(pid, timeout_s=0.2):
            return True
    return not _is_pid_alive(pid)


def _is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _safe_getpgrp() -> int | None:
    try:
        return os.getpgrp()
    except Exception:
        return None


def _load_helper_manifest_best_effort(path):
    try:
        return load_helper_manifest(path)
    except Exception:
        return None


def _canonical_runtime_generation(runtime) -> int:
    try:
        generation = int(getattr(runtime, 'runtime_generation', None))
    except Exception:
        return 0
    return generation if generation > 0 else 0


__all__ = ['cleanup_stale_runtime_helper', 'terminate_helper_manifest_path']
