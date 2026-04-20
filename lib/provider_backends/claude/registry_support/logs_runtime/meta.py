from __future__ import annotations

import json
from pathlib import Path


def read_session_meta(log_path: Path) -> tuple[str | None, str | None, bool | None]:
    try:
        with log_path.open("r", encoding="utf-8", errors="ignore") as handle:
            for _ in range(30):
                line = next_meta_line(handle)
                if line is None:
                    break
                entry = parse_meta_entry(line)
                if entry is None:
                    continue
                meta = session_meta_tuple(entry)
                if meta is not None:
                    return meta
    except OSError:
        return None, None, None
    return None, None, None


def next_meta_line(handle) -> str | None:
    line = handle.readline()
    if not line:
        return None
    return line.strip()


def parse_meta_entry(line: str) -> dict | None:
    if not line:
        return None
    try:
        entry = json.loads(line)
    except Exception:
        return None
    return entry if isinstance(entry, dict) else None


def session_meta_tuple(
    entry: dict,
) -> tuple[str | None, str | None, bool | None] | None:
    cwd_str = normalized_meta_text(entry.get("cwd") or entry.get("projectPath"))
    sid_str = normalized_meta_text(entry.get("sessionId") or entry.get("id"))
    sidechain_bool = sidechain_flag(entry.get("isSidechain"))
    if cwd_str or sid_str:
        return cwd_str, sid_str, sidechain_bool
    return None


def normalized_meta_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def sidechain_flag(value: object) -> bool | None:
    if value is True:
        return True
    if value is False:
        return False
    return None


__all__ = ["read_session_meta"]
