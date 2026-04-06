from __future__ import annotations

import json
import os
from pathlib import Path


def env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return max(0.0, value)


def path_or_none(value: object) -> Path | None:
    raw = str(value or '').strip()
    if not raw:
        return None
    try:
        return Path(raw).expanduser()
    except Exception:
        return None


def read_session_data(path: Path) -> dict[str, object]:
    try:
        data = json.loads(path.read_text(encoding='utf-8-sig'))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def session_work_dir(data: dict[str, object]) -> Path | None:
    for key in ('work_dir', 'workspace_path', 'start_dir'):
        raw = str(data.get(key) or '').strip()
        if not raw:
            continue
        try:
            return Path(raw).expanduser()
        except Exception:
            continue
    return None


def session_root(data: dict[str, object]) -> Path:
    raw_root = str(data.get('codex_session_root') or os.environ.get('CODEX_SESSION_ROOT') or '').strip()
    if raw_root:
        return Path(raw_root).expanduser()
    raw_home = str(data.get('codex_home') or os.environ.get('CODEX_HOME') or '').strip()
    if raw_home:
        return Path(raw_home).expanduser() / 'sessions'
    return Path.home() / '.codex' / 'sessions'


__all__ = ['env_float', 'path_or_none', 'read_session_data', 'session_root', 'session_work_dir']
