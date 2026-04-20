from __future__ import annotations

import locale
import os
import sys


def decode_stdin_bytes(data: bytes) -> str:
    """Decode raw stdin bytes robustly without emitting surrogates."""
    if not data:
        return ""

    decoded = _decode_with_bom(data)
    if decoded is not None:
        return decoded

    forced_encoding = _forced_stdin_encoding()
    if forced_encoding is not None:
        return _decode_forced(data, forced_encoding)

    decoded = _decode_utf8_strict(data)
    if decoded is not None:
        return decoded

    decoded = _decode_preferred_locale(data)
    if decoded is not None:
        return decoded

    decoded = _decode_windows_mbcs(data)
    if decoded is not None:
        return decoded

    return data.decode("utf-8", errors="replace")


def _decode_with_bom(data: bytes) -> str | None:
    if data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig", errors="strict")
    if data.startswith(b"\xff\xfe"):
        return data[2:].decode("utf-16le", errors="strict")
    if data.startswith(b"\xfe\xff"):
        return data[2:].decode("utf-16be", errors="strict")
    return None


def _forced_stdin_encoding() -> str | None:
    value = (os.environ.get("CCB_STDIN_ENCODING") or "").strip()
    return value or None


def _decode_forced(data: bytes, encoding: str) -> str:
    try:
        return data.decode(encoding, errors="strict")
    except Exception:
        return data.decode(encoding, errors="replace")


def _decode_utf8_strict(data: bytes) -> str | None:
    try:
        return data.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return None


def _decode_preferred_locale(data: bytes) -> str | None:
    preferred = (locale.getpreferredencoding(False) or "").strip()
    if not preferred:
        return None
    try:
        return data.decode(preferred, errors="strict")
    except (LookupError, UnicodeDecodeError):
        return None


def _decode_windows_mbcs(data: bytes) -> str | None:
    if sys.platform != "win32":
        return None
    try:
        return data.decode("mbcs", errors="strict")
    except Exception:
        return None
