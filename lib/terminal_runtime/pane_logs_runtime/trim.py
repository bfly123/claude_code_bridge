from __future__ import annotations

import os
import tempfile
from pathlib import Path

from terminal_runtime.env import env_int


def maybe_trim_log(path: Path) -> None:
    max_bytes = max(0, env_int('CCB_PANE_LOG_MAX_BYTES', 10 * 1024 * 1024))
    if max_bytes <= 0:
        return
    try:
        size = path.stat().st_size
    except Exception:
        return
    if size <= max_bytes:
        return
    tail = read_log_tail(path, max_bytes=max_bytes)
    if tail is None:
        return
    replace_log_with_tail(path, tail=tail)


def read_log_tail(path: Path, *, max_bytes: int) -> bytes | None:
    try:
        with path.open('rb') as handle:
            handle.seek(-max_bytes, os.SEEK_END)
            return handle.read()
    except Exception:
        return None


def replace_log_with_tail(path: Path, *, tail: bytes) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=f'.{path.name}.', suffix='.tmp', dir=str(path.parent))
        try:
            with os.fdopen(fd, 'wb') as out:
                out.write(tail)
            os.replace(tmp_name, path)
        finally:
            try:
                os.unlink(tmp_name)
            except Exception:
                pass
    except Exception:
        return


__all__ = ['maybe_trim_log', 'read_log_tail', 'replace_log_with_tail']
