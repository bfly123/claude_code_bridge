from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, Tuple

from env_utils import env_bool
from providers import ProviderClientSpec


def autostart_enabled(primary_env: str, legacy_env: str, default: bool = True) -> bool:
    if primary_env in os.environ:
        return env_bool(primary_env, default)
    if legacy_env in os.environ:
        return env_bool(legacy_env, default)
    return default


def state_file_from_env(env_name: str) -> Optional[Path]:
    raw = (os.environ.get(env_name) or "").strip()
    if not raw:
        return None
    try:
        return Path(raw).expanduser()
    except Exception:
        return None


def find_project_session_file(work_dir: Path, session_filename: str) -> Optional[Path]:
    current = Path(work_dir).resolve()
    while True:
        candidate = current / session_filename
        if candidate.exists():
            return candidate
        if current == current.parent:
            return None
        current = current.parent


def try_daemon_request(spec: ProviderClientSpec, work_dir: Path, message: str, timeout: float, quiet: bool, state_file: Optional[Path] = None) -> Optional[Tuple[str, int]]:
    if not env_bool(spec.enabled_env, True):
        return None

    if not find_project_session_file(work_dir, spec.session_filename):
        return None

    from importlib import import_module
    daemon_module = import_module(spec.daemon_module)
    read_state = getattr(daemon_module, "read_state")

    st = read_state(state_file=state_file)
    if not st:
        return None
    try:
        host = st.get("connect_host") or st.get("host")
        port = int(st["port"])
        token = st["token"]
    except Exception:
        return None

    try:
        payload = {
            "type": f"{spec.protocol_prefix}.request",
            "v": 1,
            "id": f"{spec.protocol_prefix}-{os.getpid()}-{int(time.time() * 1000)}",
            "token": token,
            "work_dir": str(work_dir),
            "timeout_s": float(timeout),
            "quiet": bool(quiet),
            "message": message,
        }
        connect_timeout = min(1.0, max(0.1, float(timeout)))
        with socket.create_connection((host, port), timeout=connect_timeout) as sock:
            sock.settimeout(0.5)
            sock.sendall((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
            buf = b""
            deadline = time.time() + float(timeout) + 5.0
            while b"\n" not in buf and time.time() < deadline:
                try:
                    chunk = sock.recv(65536)
                except socket.timeout:
                    continue
                if not chunk:
                    break
                buf += chunk
            if b"\n" not in buf:
                return None
            line = buf.split(b"\n", 1)[0].decode("utf-8", errors="replace")
            resp = json.loads(line)
            if resp.get("type") != f"{spec.protocol_prefix}.response":
                return None
            reply = str(resp.get("reply") or "")
            exit_code = int(resp.get("exit_code", 1))
            return reply, exit_code
    except Exception:
        return None


def maybe_start_daemon(spec: ProviderClientSpec, work_dir: Path) -> bool:
    if not env_bool(spec.enabled_env, True):
        return False
    if not autostart_enabled(spec.autostart_env_primary, spec.autostart_env_legacy, True):
        return False
    if not find_project_session_file(work_dir, spec.session_filename):
        return False

    candidates: list[str] = []
    local = (Path(__file__).resolve().parent.parent / "bin" / spec.daemon_bin_name)
    if local.exists():
        candidates.append(str(local))
    found = shutil.which(spec.daemon_bin_name)
    if found:
        candidates.append(found)
    if not candidates:
        return False

    entry = candidates[0]
    lower = entry.lower()
    if lower.endswith((".cmd", ".bat", ".exe")):
        argv = [entry]
    else:
        argv = [sys.executable, entry]
    try:
        kwargs = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "close_fds": True}
        if os.name == "nt":
            kwargs["creationflags"] = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        else:
            kwargs["start_new_session"] = True
        subprocess.Popen(argv, **kwargs)
        return True
    except Exception:
        return False


def wait_for_daemon_ready(spec: ProviderClientSpec, timeout_s: float = 2.0, state_file: Optional[Path] = None) -> bool:
    try:
        from importlib import import_module
        daemon_module = import_module(spec.daemon_module)
        ping_daemon = getattr(daemon_module, "ping_daemon")
    except Exception:
        return False
    deadline = time.time() + max(0.1, float(timeout_s))
    if state_file is None:
        state_file = state_file_from_env(spec.state_file_env)
    while time.time() < deadline:
        try:
            if ping_daemon(timeout_s=0.2, state_file=state_file):
                return True
        except Exception:
            pass
        time.sleep(0.1)
    return False


def check_background_mode() -> bool:
    if os.environ.get("CLAUDECODE") != "1":
        return True
    if os.environ.get("CCB_ALLOW_FOREGROUND") in ("1", "true", "yes"):
        return True
    try:
        import stat
        mode = os.fstat(sys.stdout.fileno()).st_mode
        return stat.S_ISREG(mode) or stat.S_ISSOCK(mode) or stat.S_ISFIFO(mode)
    except Exception:
        return False
