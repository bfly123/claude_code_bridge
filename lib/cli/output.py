from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Optional


EXIT_OK = 0
EXIT_ERROR = 1
EXIT_NO_REPLY = 2


def atomic_write_text(path: Path, content: str, *, encoding: str = "utf-8") -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fd: Optional[int] = None
    tmp_path: Optional[str] = None
    try:
        fd, tmp_path = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
        with os.fdopen(fd, "w", encoding=encoding, newline="\n") as handle:
            handle.write(content)
        fd = None
        os.replace(tmp_path, path)
        tmp_path = None
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except Exception:
                pass
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


def normalize_message_parts(parts: list[str]) -> str:
    return " ".join(parts).strip()


__all__ = [
    "EXIT_OK",
    "EXIT_ERROR",
    "EXIT_NO_REPLY",
    "atomic_write_text",
    "normalize_message_parts",
]
