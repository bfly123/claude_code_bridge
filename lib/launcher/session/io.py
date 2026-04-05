from __future__ import annotations

import json
from pathlib import Path
import time
from typing import Callable


def read_session_json(path: Path) -> dict:
    try:
        if not Path(path).exists():
            return {}
        raw = Path(path).read_text(encoding="utf-8-sig")
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def write_session_json(path: Path, data: dict) -> None:
    try:
        path = Path(path)
        if not path.parent.is_dir():
            raise FileNotFoundError(str(path.parent))
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def mark_session_inactive(
    path: Path,
    *,
    safe_write_session_fn: Callable[[Path, str], tuple[bool, str | None]],
    ended_at: str | None = None,
) -> None:
    data = read_session_json(path)
    if not data:
        return
    data["active"] = False
    data["ended_at"] = ended_at or time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        safe_write_session_fn(path, json.dumps(data, ensure_ascii=False, indent=2))
    except Exception:
        pass
