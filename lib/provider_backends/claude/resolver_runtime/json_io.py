from __future__ import annotations

import json
from pathlib import Path


def read_json(path: Path) -> dict:
    try:
        raw = path.read_text(encoding="utf-8-sig", errors="replace")
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


__all__ = ["read_json"]
