from __future__ import annotations

import json
from pathlib import Path


def read_droid_session_start(session_path: Path, *, max_lines: int = 30) -> tuple[str | None, str | None]:
    try:
        with session_path.open("r", encoding="utf-8", errors="replace") as handle:
            for _ in range(max_lines):
                entry = _read_json_line(handle.readline())
                if entry is None:
                    continue
                if entry.get("type") != "session_start":
                    continue
                return _normalize_field(entry.get("cwd")), _normalize_field(entry.get("id"))
    except OSError:
        return None, None
    return None, None


def _read_json_line(line: str) -> dict | None:
    text = line.strip()
    if not text:
        return None
    try:
        entry = json.loads(text)
    except Exception:
        return None
    return entry if isinstance(entry, dict) else None


def _normalize_field(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


__all__ = ["read_droid_session_start"]
