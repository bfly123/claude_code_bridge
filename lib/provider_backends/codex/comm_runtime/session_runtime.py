from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Callable, Optional

from provider_sessions.files import find_project_session_file


def find_codex_session_file(*, cwd: Path | None = None) -> Optional[Path]:
    env_session = (os.environ.get("CCB_SESSION_FILE") or "").strip()
    if env_session:
        try:
            session_path = Path(os.path.expanduser(env_session))
            if _is_codex_session_filename(session_path.name) and session_path.is_file():
                return session_path
        except Exception:
            pass
    return find_project_session_file(cwd or Path.cwd(), ".codex-session")


def load_codex_session_info(*, session_finder: Callable[[], Optional[Path]]):
    if "CCB_SESSION_ID" in os.environ:
        result = {
            "ccb_session_id": os.environ["CCB_SESSION_ID"],
            "runtime_dir": os.environ["CODEX_RUNTIME_DIR"],
            "input_fifo": os.environ["CODEX_INPUT_FIFO"],
            "output_fifo": os.environ.get("CODEX_OUTPUT_FIFO", ""),
            "terminal": os.environ.get("CODEX_TERMINAL", "tmux"),
            "tmux_session": os.environ.get("CODEX_TMUX_SESSION", ""),
            "pane_id": os.environ.get("CODEX_TMUX_SESSION", ""),
            "_session_file": None,
        }
        session_file = session_finder()
        if session_file:
            try:
                with open(session_file, "r", encoding="utf-8-sig") as handle:
                    file_data = json.load(handle)
                if isinstance(file_data, dict):
                    result["codex_session_path"] = file_data.get("codex_session_path")
                    result["codex_session_id"] = file_data.get("codex_session_id")
                    result["_session_file"] = str(session_file)
            except Exception:
                pass
        return result

    project_session = session_finder()
    if not project_session:
        return None

    try:
        with open(project_session, "r", encoding="utf-8-sig") as handle:
            data = json.load(handle)
    except Exception:
        return None

    if not isinstance(data, dict):
        return None
    if not data.get("active", False):
        return None

    runtime_dir = Path(data.get("runtime_dir", ""))
    if not runtime_dir.exists():
        return None

    data["_session_file"] = str(project_session)
    return data


def check_tmux_runtime_health(*, runtime_dir: Path, input_fifo: Path) -> tuple[bool, str]:
    codex_pid_file = runtime_dir / "codex.pid"
    if not codex_pid_file.exists():
        return False, "Codex process PID file not found"

    with open(codex_pid_file, "r", encoding="utf-8") as handle:
        codex_pid = int(handle.read().strip())
    healthy, status = _probe_pid(codex_pid, label="Codex process")
    if not healthy:
        return healthy, status

    bridge_pid_file = runtime_dir / "bridge.pid"
    if not bridge_pid_file.exists():
        return False, "Bridge process PID file not found"
    try:
        with bridge_pid_file.open("r", encoding="utf-8") as handle:
            bridge_pid = int(handle.read().strip())
    except Exception:
        return False, "Failed to read bridge process PID"
    healthy, status = _probe_pid(bridge_pid, label="Bridge process")
    if not healthy:
        return healthy, status

    if not input_fifo.exists():
        return False, "Communication pipe does not exist"
    return True, "Session healthy"


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


def _is_codex_session_filename(filename: str) -> bool:
    name = str(filename or "").strip()
    if name == ".codex-session":
        return True
    return name.startswith(".codex-") and name.endswith("-session")
