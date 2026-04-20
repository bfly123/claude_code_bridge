from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from storage.atomic import atomic_write_json


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}
    return dict(data) if isinstance(data, dict) else {}


def save_json(path: Path, payload: dict[str, Any]) -> Path:
    atomic_write_json(path, payload)
    return path


def workspace_key(workspace_path: Path) -> str:
    try:
        return str(Path(workspace_path).expanduser().resolve())
    except Exception:
        return str(Path(workspace_path).expanduser())


__all__ = ['load_json', 'save_json', 'workspace_key']
