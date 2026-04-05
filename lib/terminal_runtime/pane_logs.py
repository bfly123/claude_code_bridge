from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path

from .env import env_float, env_int, sanitize_filename

_LAST_PANE_LOG_CLEAN: float = 0.0


def pane_log_root() -> Path:
    try:
        from ccbd.runtime import run_dir
    except Exception:
        return Path.home() / ".cache" / "ccb"
    return run_dir() / "pane-logs"


def pane_log_dir(backend: str, socket_name: str | None) -> Path:
    root = pane_log_root()
    if backend == "tmux":
        if socket_name:
            safe = sanitize_filename(socket_name) or "default"
            return root / f"tmux-{safe}"
        return root / "tmux"
    safe_backend = sanitize_filename(backend) or "pane"
    return root / safe_backend


def pane_log_path_for(pane_id: str, backend: str, socket_name: str | None) -> Path:
    pane = (pane_id or "").strip().replace("%", "")
    safe = sanitize_filename(pane) or "pane"
    return pane_log_dir(backend, socket_name) / f"pane-{safe}.log"


def maybe_trim_log(path: Path) -> None:
    max_bytes = max(0, env_int("CCB_PANE_LOG_MAX_BYTES", 10 * 1024 * 1024))
    if max_bytes <= 0:
        return
    try:
        size = path.stat().st_size
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


def cleanup_pane_logs(dir_path: Path) -> None:
    global _LAST_PANE_LOG_CLEAN
    interval_s = env_float("CCB_PANE_LOG_CLEAN_INTERVAL_S", 600.0)
    now = time.time()
    if interval_s and (now - _LAST_PANE_LOG_CLEAN) < interval_s:
        return
    _LAST_PANE_LOG_CLEAN = now

    ttl_days = env_int("CCB_PANE_LOG_TTL_DAYS", 7)
    max_files = env_int("CCB_PANE_LOG_MAX_FILES", 200)
    if ttl_days <= 0 and max_files <= 0:
        return

    try:
        if not dir_path.exists():
            return
    except Exception:
        return

    files: list[Path] = []
    try:
        for entry in dir_path.iterdir():
            if entry.is_file():
                files.append(entry)
    except Exception:
        return

    if ttl_days > 0:
        cutoff = now - (ttl_days * 86400)
        for path in list(files):
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink(missing_ok=True)
                    files.remove(path)
            except Exception:
                continue

    if max_files > 0 and len(files) > max_files:
        try:
            files.sort(key=lambda path: path.stat().st_mtime)
        except Exception:
            files.sort(key=lambda path: path.name)
        extra = len(files) - max_files
        for path in files[:extra]:
            try:
                path.unlink(missing_ok=True)
            except Exception:
                continue
