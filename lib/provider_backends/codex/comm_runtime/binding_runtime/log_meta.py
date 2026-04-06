from __future__ import annotations

from pathlib import Path

from .common import load_first_entry


def extract_cwd_from_log_file(log_path: Path) -> str | None:
    entry = load_first_entry(log_path)
    if entry is None or entry.get("type") != "session_meta":
        return None
    payload = entry.get("payload", {})
    cwd = payload.get("cwd") if isinstance(payload, dict) else None
    if isinstance(cwd, str) and cwd.strip():
        return cwd.strip()
    return None


__all__ = ["extract_cwd_from_log_file"]
