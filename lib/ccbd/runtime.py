from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path

from env_utils import env_int


def run_dir() -> Path:
    override = (os.environ.get("CCB_RUN_DIR") or "").strip()
    if override:
        return Path(override).expanduser()

    if os.name == "nt":
        base = (os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or "").strip()
        if base:
            return Path(base) / "ccb"
        return Path.home() / "AppData" / "Local" / "ccb"

    xdg_cache = (os.environ.get("XDG_CACHE_HOME") or "").strip()
    if xdg_cache:
        return Path(xdg_cache) / "ccb"
    return Path.home() / ".cache" / "ccb"


def state_file_path(name: str) -> Path:
    if name.endswith(".json"):
        return run_dir() / name
    return run_dir() / f"{name}.json"


def log_path(name: str) -> Path:
    if name.endswith(".log"):
        return run_dir() / name
    return run_dir() / f"{name}.log"


_LAST_LOG_SHRINK_CHECK: dict[str, float] = {}


def _maybe_shrink_log(path: Path) -> None:
    max_bytes = max(0, env_int("CCB_LOG_MAX_BYTES", 2 * 1024 * 1024))
    if max_bytes <= 0:
        return

    interval_s = max(0.0, float(env_int("CCB_LOG_SHRINK_CHECK_INTERVAL_S", 10)))
    key = str(path)
    now = time.time()
    last = _LAST_LOG_SHRINK_CHECK.get(key, 0.0)
    if interval_s and (now - last) < interval_s:
        return
    _LAST_LOG_SHRINK_CHECK[key] = now

    try:
        st = path.stat()
        size = int(st.st_size)
    except Exception:
        return

    if size <= max_bytes:
        return

    try:
        with path.open("rb") as handle:
            handle.seek(-max_bytes, os.SEEK_END)
            tail = handle.read()
    except Exception:
        return

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
        try:
            with os.fdopen(fd, "wb") as out:
                out.write(tail)
            os.replace(tmp_name, path)
        finally:
            try:
                os.unlink(tmp_name)
            except Exception:
                pass
    except Exception:
        return


def write_log(path: Path, msg: str) -> None:
    try:
        _maybe_shrink_log(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(msg.rstrip() + "\n")
    except Exception:
        pass


def random_token() -> str:
    return os.urandom(16).hex()


def normalize_connect_host(host: str) -> str:
    host = (host or "").strip()
    if not host or host in ("0.0.0.0",):
        return "127.0.0.1"
    if host in ("::", "[::]"):
        return "::1"
    return host


def get_daemon_work_dir(state_file_name: str = "ccbd.json") -> Path | None:
    try:
        state_path = state_file_path(state_file_name)
        if not state_path.exists():
            return None
        with state_path.open("r", encoding="utf-8") as handle:
            import json

            state = json.load(handle)
        if not isinstance(state, dict):
            return None
        work_dir = state.get("work_dir")
        if not work_dir or not isinstance(work_dir, str):
            return None
        return Path(work_dir.strip())
    except Exception:
        return None


__all__ = ['get_daemon_work_dir', 'log_path', 'normalize_connect_host', 'random_token', 'run_dir', 'state_file_path', 'write_log']
