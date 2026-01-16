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
from session_utils import find_project_session_file
from project_id import compute_ccb_project_id
from pane_registry import load_registry_by_project_id


def resolve_work_dir(
    spec: ProviderClientSpec,
    *,
    cli_session_file: str | None = None,
    env_session_file: str | None = None,
    default_cwd: Path | None = None,
) -> tuple[Path, Path | None]:
    """
    Resolve work_dir for a provider, optionally overriding cwd via an explicit session file path.

    Priority:
      1) cli_session_file (--session-file)
      2) env_session_file (CCB_SESSION_FILE)
      3) default_cwd / Path.cwd()

    Returns:
      (work_dir, session_file_or_none)
    """
    raw = (cli_session_file or "").strip() or (env_session_file or "").strip()
    if not raw:
        return (default_cwd or Path.cwd()), None

    expanded = os.path.expanduser(raw)
    session_path = Path(expanded)

    # In Claude Code, require absolute path to avoid shell snapshot cwd pollution.
    if os.environ.get("CLAUDECODE") == "1" and not session_path.is_absolute():
        raise ValueError(f"--session-file must be an absolute path in Claude Code (got: {raw})")

    try:
        session_path = session_path.resolve()
    except Exception:
        session_path = Path(expanded).absolute()

    if session_path.name != spec.session_filename:
        raise ValueError(
            f"Invalid session file for {spec.protocol_prefix}: expected filename {spec.session_filename}, got {session_path.name}"
        )
    if not session_path.exists():
        raise ValueError(f"Session file not found: {session_path}")
    if not session_path.is_file():
        raise ValueError(f"Session file must be a file: {session_path}")

    # New layout: session files live under `<project>/.ccb_config/<session_filename>`.
    # In that case work_dir is the parent directory of `.ccb_config/`.
    if session_path.parent.name == ".ccb_config":
        return session_path.parent.parent, session_path
    return session_path.parent, session_path


def resolve_work_dir_with_registry(
    spec: ProviderClientSpec,
    *,
    provider: str,
    cli_session_file: str | None = None,
    env_session_file: str | None = None,
    default_cwd: Path | None = None,
    registry_only_env: str = "CCB_REGISTRY_ONLY",
) -> tuple[Path, Path | None]:
    """
    Resolve work_dir, additionally supporting registry routing by ccb_project_id.

    Priority:
      1) cli_session_file (--session-file)
      2) env_session_file (CCB_SESSION_FILE)
      3) registry lookup by ccb_project_id + provider
      4) default_cwd / Path.cwd()
    """
    raw = (cli_session_file or "").strip() or (env_session_file or "").strip()
    if raw:
        return resolve_work_dir(
            spec,
            cli_session_file=cli_session_file,
            env_session_file=env_session_file,
            default_cwd=default_cwd,
        )

    cwd = default_cwd or Path.cwd()
    try:
        project_id = compute_ccb_project_id(cwd)
    except Exception:
        project_id = ""
    if project_id:
        rec = load_registry_by_project_id(project_id, provider)
        if isinstance(rec, dict):
            providers = rec.get("providers") if isinstance(rec.get("providers"), dict) else {}
            entry = providers.get(str(provider).strip().lower()) if isinstance(providers, dict) else None
            session_file = None
            if isinstance(entry, dict):
                sf = entry.get("session_file")
                if isinstance(sf, str) and sf.strip():
                    session_file = sf.strip()
            if not session_file:
                wd = rec.get("work_dir")
                if isinstance(wd, str) and wd.strip():
                    try:
                        found = find_project_session_file(Path(wd.strip()), spec.session_filename)
                    except Exception:
                        found = None
                    if found:
                        session_file = str(found)
                    else:
                        session_file = str(Path(wd.strip()) / ".ccb_config" / spec.session_filename)
            if session_file:
                try:
                    return resolve_work_dir(
                        spec,
                        cli_session_file=session_file,
                        env_session_file=None,
                        default_cwd=cwd,
                    )
                except Exception:
                    pass

    if env_bool(registry_only_env, False):
        raise ValueError(f"{registry_only_env}=1: registry routing failed for provider={provider!r} cwd={cwd}")

    return (cwd, None)


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
            deadline = None if float(timeout) < 0 else (time.time() + float(timeout) + 5.0)
            while b"\n" not in buf and (deadline is None or time.time() < deadline):
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
    # Codex CLI / tool harness environments often run commands in a PTY but are still safe to run in
    # foreground (the assistant controls execution). Allow these to avoid false failures.
    if os.environ.get("CODEX_RUNTIME_DIR") or os.environ.get("CODEX_SESSION_ID"):
        return True
    try:
        import stat
        mode = os.fstat(sys.stdout.fileno()).st_mode
        return stat.S_ISREG(mode) or stat.S_ISSOCK(mode) or stat.S_ISFIFO(mode)
    except Exception:
        return False
