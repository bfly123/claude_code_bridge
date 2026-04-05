"""Windows compatibility utilities"""
from __future__ import annotations

import locale
import os
import sys

def setup_windows_encoding():
    """Configure UTF-8 encoding for Windows console"""
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def decode_stdin_bytes(data: bytes) -> str:
    """Decode raw stdin bytes robustly (especially on Windows).

    Goal: avoid lone surrogates (e.g. \\udc80) that later crash UTF-8 encoding.
    Strategy:
      1) Honor BOMs (UTF-8/UTF-16).
      2) Try UTF-8 strictly (common for Git Bash / PowerShell 7).
      3) Fallback to locale preferred encoding (common for Windows PowerShell 5.1 / cmd).
      4) Windows fallback: mbcs (ANSI code page).
      5) Last resort: UTF-8 with replacement.

    Users can override via CCB_STDIN_ENCODING.
    """
    if not data:
        return ""

    # BOM detection first.
    if data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig", errors="strict")
    if data.startswith(b"\xff\xfe"):
        return data[2:].decode("utf-16le", errors="strict")
    if data.startswith(b"\xfe\xff"):
        return data[2:].decode("utf-16be", errors="strict")

    forced = (os.environ.get("CCB_STDIN_ENCODING") or "").strip()
    if forced:
        try:
            return data.decode(forced, errors="strict")
        except Exception:
            return data.decode(forced, errors="replace")

    try:
        return data.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        pass

    preferred = (locale.getpreferredencoding(False) or "").strip()
    if preferred:
        try:
            return data.decode(preferred, errors="strict")
        except UnicodeDecodeError:
            pass
        except LookupError:
            pass

    if sys.platform == "win32":
        try:
            return data.decode("mbcs", errors="strict")
        except Exception:
            pass

    return data.decode("utf-8", errors="replace")


def read_stdin_text() -> str:
    """Read all text from stdin (non-interactive) using robust decoding."""
    try:
        buf = sys.stdin.buffer  # type: ignore[attr-defined]
    except Exception:
        # Fallback: whatever Python thinks stdin is.
        return sys.stdin.read()
    return decode_stdin_bytes(buf.read())
