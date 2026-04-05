from __future__ import annotations

from pathlib import Path
from typing import Callable, Mapping

CCBD_RUNTIME_NAME = "ccbd"
CCBD_RPC_PREFIX = "ask"
CCBD_STATE_FILE_NAME = "ccbd.json"


def terminate_provider_daemon(
    provider: str,
    *,
    specs_by_provider: Mapping[str, object],
    state_file_path_fn: Callable[[str], Path],
    shutdown_daemon_fn: Callable[[str, float, Path], bool],
    read_state_fn: Callable[[Path], dict | None],
    kill_pid_fn: Callable[[int], bool] | Callable[[int, bool], bool],
) -> None:
    spec = specs_by_provider.get(provider)
    if spec is None:
        return

    state_file = state_file_path_fn(CCBD_STATE_FILE_NAME)
    try:
        if shutdown_daemon_fn(CCBD_RPC_PREFIX, 1.0, state_file):
            print(f"✅ {CCBD_RUNTIME_NAME} runtime shutdown requested")
            return
        state = read_state_fn(state_file)
        if state and state.get("pid"):
            pid = int(state["pid"])
            if kill_pid_fn(pid, force=True):
                print(f"✅ {CCBD_RUNTIME_NAME} runtime force killed (pid={pid})")
            else:
                print(f"⚠️ {CCBD_RUNTIME_NAME} runtime could not be killed (pid={pid})")
    except Exception:
        pass


__all__ = ["terminate_provider_daemon"]
