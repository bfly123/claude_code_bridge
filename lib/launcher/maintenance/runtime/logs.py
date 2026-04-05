from __future__ import annotations

import os
from pathlib import Path

from env_utils import env_bool, env_float


def shrink_ccb_logs() -> int:
    if not env_bool("CCB_LOG_SHRINK", True):
        return 0

    try:
        max_bytes = max(0, int(env_float("CCB_LOG_MAX_BYTES", 2 * 1024 * 1024)))
    except Exception:
        max_bytes = 2 * 1024 * 1024
    if max_bytes <= 0:
        return 0

    cache_dir: Path | None = None
    xdg_cache = (os.environ.get("XDG_CACHE_HOME") or "").strip()
    if xdg_cache:
        cache_dir = Path(xdg_cache) / "ccb"
    else:
        cache_dir = Path.home() / ".cache" / "ccb"

    fallback_run_dir = Path.home() / ".ccb" / "run"

    def _shrink_file(path: Path) -> bool:
        try:
            if not path.exists() or not path.is_file():
                return False
            size = path.stat().st_size
            if size <= max_bytes:
                return False
            with path.open("rb") as handle:
                handle.seek(-max_bytes, os.SEEK_END)
                tail = handle.read()
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_bytes(tail)
            os.replace(tmp, path)
            return True
        except Exception:
            try:
                tmp = path.with_suffix(path.suffix + ".tmp")
                if tmp.exists():
                    tmp.unlink()
            except Exception:
                pass
            return False

    removed = 0
    for base in (cache_dir, fallback_run_dir):
        try:
            if not base.exists() or not base.is_dir():
                continue
        except Exception:
            continue
        try:
            for log_file in base.glob("*.log"):
                if _shrink_file(log_file):
                    removed += 1
        except Exception:
            continue
    return removed
