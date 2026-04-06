from __future__ import annotations

import os
import subprocess
from pathlib import Path


def check_tmux_runtime_health(*, runtime_dir: Path, input_fifo: Path) -> tuple[bool, str]:
    codex_pid, codex_error = _try_read_pid(
        runtime_dir / "codex.pid",
        missing_message="Codex process PID file not found",
        invalid_message="Failed to read Codex process PID",
    )
    if codex_error:
        return False, codex_error
    healthy, status = _probe_pid(codex_pid, label="Codex process")
    if not healthy:
        return healthy, status

    bridge_pid, bridge_error = _try_read_pid(
        runtime_dir / "bridge.pid",
        missing_message="Bridge process PID file not found",
        invalid_message="Failed to read bridge process PID",
    )
    if bridge_error:
        return False, bridge_error
    healthy, status = _probe_pid(bridge_pid, label="Bridge process")
    if not healthy:
        return healthy, status

    if not input_fifo.exists():
        return False, "Communication pipe does not exist"
    return True, "Session healthy"


def _try_read_pid(pid_file: Path, *, missing_message: str, invalid_message: str) -> tuple[int, str | None]:
    if not pid_file.exists():
        return 0, missing_message
    try:
        with pid_file.open("r", encoding="utf-8") as handle:
            return int(handle.read().strip()), None
    except Exception:
        return 0, invalid_message


def _probe_pid(pid: int, *, label: str) -> tuple[bool, str]:
    try:
        os.kill(pid, 0)
    except PermissionError:
        try:
            result = subprocess.run(["ps", "-p", str(pid)], capture_output=True, timeout=2)
            if result.returncode != 0:
                return False, f"{label} (PID:{pid}) has exited"
        except Exception:
            pass
    except OSError:
        return False, f"{label} (PID:{pid}) has exited"
    return True, "Session healthy"


__all__ = ["check_tmux_runtime_health"]
