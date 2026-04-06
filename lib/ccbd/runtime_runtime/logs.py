from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path

from runtime_env import env_int


_LAST_LOG_SHRINK_CHECK: dict[str, float] = {}


def _should_check_shrink(path: Path, *, interval_s: float) -> bool:
    key = str(path)
    now = time.time()
    last = _LAST_LOG_SHRINK_CHECK.get(key, 0.0)
    if interval_s and (now - last) < interval_s:
        return False
    _LAST_LOG_SHRINK_CHECK[key] = now
    return True


def _read_tail_bytes(path: Path, *, max_bytes: int) -> bytes | None:
    try:
        size = int(path.stat().st_size)
    except Exception:
        return None
    if size <= max_bytes:
        return None
    try:
        with path.open("rb") as handle:
            handle.seek(-max_bytes, os.SEEK_END)
            return handle.read()
    except Exception:
        return None


def _replace_with_tail(path: Path, *, tail: bytes) -> None:
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


def _maybe_shrink_log(path: Path) -> None:
    max_bytes = max(0, env_int("CCB_LOG_MAX_BYTES", 2 * 1024 * 1024))
    if max_bytes <= 0:
        return

    interval_s = max(0.0, float(env_int("CCB_LOG_SHRINK_CHECK_INTERVAL_S", 10)))
    if not _should_check_shrink(path, interval_s=interval_s):
        return

    tail = _read_tail_bytes(path, max_bytes=max_bytes)
    if tail is None:
        return

    try:
        _replace_with_tail(path, tail=tail)
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


__all__ = ["write_log"]
