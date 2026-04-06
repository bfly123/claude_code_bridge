from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_first_line(log_path: Path) -> str | None:
    try:
        with log_path.open("r", encoding="utf-8") as handle:
            first_line = handle.readline()
    except OSError:
        return None
    return first_line or None


def load_first_entry(log_path: Path) -> dict[str, Any] | None:
    first_line = read_first_line(log_path)
    if not first_line:
        return None
    try:
        entry = json.loads(first_line)
    except Exception:
        return None
    return entry if isinstance(entry, dict) else None


__all__ = ["load_first_entry", "read_first_line"]
