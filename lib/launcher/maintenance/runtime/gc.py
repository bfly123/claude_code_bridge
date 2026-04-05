from __future__ import annotations

import getpass
from pathlib import Path
import shutil
import tempfile
import time

from env_utils import env_bool, env_float
from launcher.maintenance.runtime.process import is_pid_alive


def _runtime_base_dir() -> Path:
    try:
        base = Path(tempfile.gettempdir())
    except Exception:
        base = Path("/tmp")
    return base / f"claude-ai-{getpass.getuser()}"


def cleanup_stale_runtime_dirs(*, exclude: Path | None = None) -> int:
    if not env_bool("CCB_RUNTIME_GC", True):
        return 0

    min_age_s = max(0.0, float(env_float("CCB_RUNTIME_GC_MIN_AGE_S", 24 * 3600.0)))
    base = _runtime_base_dir()
    try:
        if not base.exists() or not base.is_dir():
            return 0
    except Exception:
        return 0

    exclude_resolved: str | None = None
    if exclude is not None:
        try:
            exclude_resolved = str(Path(exclude).resolve())
        except Exception:
            exclude_resolved = str(exclude)

    now = time.time()
    removed = 0
    try:
        candidates = sorted(base.glob("ai-*"), key=lambda path: path.stat().st_mtime if path.exists() else 0.0)
    except Exception:
        candidates = []

    for session_dir in candidates:
        try:
            if not session_dir.is_dir():
                continue
        except Exception:
            continue

        try:
            if exclude_resolved and str(session_dir.resolve()) == exclude_resolved:
                continue
        except Exception:
            if exclude_resolved and str(session_dir) == exclude_resolved:
                continue

        try:
            stat = session_dir.stat()
            if min_age_s and (now - float(stat.st_mtime)) < min_age_s:
                continue
        except Exception:
            continue

        alive = False
        try:
            for pid_file in session_dir.glob("**/*.pid"):
                try:
                    raw = pid_file.read_text(encoding="utf-8", errors="ignore").strip()
                    if raw.isdigit() and is_pid_alive(int(raw)):
                        alive = True
                        break
                except Exception:
                    continue
        except Exception:
            pass
        if alive:
            continue

        try:
            shutil.rmtree(session_dir, ignore_errors=True)
            removed += 1
        except Exception:
            continue

    return removed
