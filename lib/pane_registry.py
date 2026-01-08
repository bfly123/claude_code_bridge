from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any, Iterable

from cli_output import atomic_write_text

REGISTRY_PREFIX = "ccb-session-"
REGISTRY_SUFFIX = ".json"
REGISTRY_TTL_SECONDS = 7 * 24 * 60 * 60


def _debug_enabled() -> bool:
    return os.environ.get("CCB_DEBUG") in ("1", "true", "yes")


def _debug(message: str) -> None:
    if not _debug_enabled():
        return
    print(f"[DEBUG] {message}", file=sys.stderr)


def _registry_dir() -> Path:
    return Path.home() / ".ccb" / "run"


def registry_path_for_session(session_id: str) -> Path:
    return _registry_dir() / f"{REGISTRY_PREFIX}{session_id}{REGISTRY_SUFFIX}"


def _iter_registry_files() -> Iterable[Path]:
    registry_dir = _registry_dir()
    if not registry_dir.exists():
        return []
    return sorted(registry_dir.glob(f"{REGISTRY_PREFIX}*{REGISTRY_SUFFIX}"))


def _coerce_updated_at(value: Any, fallback_path: Optional[Path] = None) -> int:
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        trimmed = value.strip()
        if trimmed.isdigit():
            try:
                return int(trimmed)
            except ValueError:
                pass
    if fallback_path:
        try:
            return int(fallback_path.stat().st_mtime)
        except OSError:
            return 0
    return 0


def _is_stale(updated_at: int, now: Optional[int] = None) -> bool:
    if updated_at <= 0:
        return True
    now_ts = int(time.time()) if now is None else int(now)
    return (now_ts - updated_at) > REGISTRY_TTL_SECONDS


def _load_registry_file(path: Path) -> Optional[Dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            return data
    except Exception as exc:
        _debug(f"Failed to read registry {path}: {exc}")
    return None


def load_registry_by_session_id(session_id: str) -> Optional[Dict[str, Any]]:
    if not session_id:
        return None
    path = registry_path_for_session(session_id)
    if not path.exists():
        return None
    data = _load_registry_file(path)
    if not data:
        return None
    updated_at = _coerce_updated_at(data.get("updated_at"), path)
    if _is_stale(updated_at):
        _debug(f"Registry stale for session {session_id}: {path}")
        return None
    return data


def load_registry_by_claude_pane(pane_id: str) -> Optional[Dict[str, Any]]:
    if not pane_id:
        return None
    best: Optional[Dict[str, Any]] = None
    best_ts = -1
    for path in _iter_registry_files():
        data = _load_registry_file(path)
        if not data:
            continue
        if data.get("claude_pane_id") != pane_id:
            continue
        updated_at = _coerce_updated_at(data.get("updated_at"), path)
        if _is_stale(updated_at):
            _debug(f"Registry stale for pane {pane_id}: {path}")
            continue
        if updated_at > best_ts:
            best = data
            best_ts = updated_at
    return best


def upsert_registry(record: Dict[str, Any]) -> bool:
    session_id = record.get("ccb_session_id")
    if not session_id:
        _debug("Registry update skipped: missing ccb_session_id")
        return False
    path = registry_path_for_session(str(session_id))
    path.parent.mkdir(parents=True, exist_ok=True)

    data: Dict[str, Any] = {}
    if path.exists():
        existing = _load_registry_file(path)
        if isinstance(existing, dict):
            data.update(existing)

    for key, value in record.items():
        if value is None:
            continue
        data[key] = value

    data["updated_at"] = int(time.time())

    try:
        atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2))
        return True
    except Exception as exc:
        _debug(f"Failed to write registry {path}: {exc}")
        return False
