from __future__ import annotations

import io
import sys

from .decoding import decode_stdin_bytes


def setup_windows_encoding() -> None:
    """Configure UTF-8 encoding for the Windows console."""
    if sys.platform != "win32":
        return
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def read_stdin_text() -> str:
    """Read all text from stdin using the shared decoding policy."""
    buffer = _stdin_buffer()
    if buffer is None:
        return sys.stdin.read()
    return decode_stdin_bytes(buffer.read())


def _stdin_buffer():
    try:
        return sys.stdin.buffer  # type: ignore[attr-defined]
    except Exception:
        return None
