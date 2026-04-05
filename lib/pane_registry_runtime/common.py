from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from provider_core.runtime_specs import parse_qualified_provider
from terminal_runtime import get_backend_for_session

REGISTRY_PREFIX = "ccb-session-"
REGISTRY_SUFFIX = ".json"
REGISTRY_TTL_SECONDS = 7 * 24 * 60 * 60


def debug_enabled() -> bool:
    return os.environ.get("CCB_DEBUG") in ("1", "true", "yes")


def debug(message: str) -> None:
    if not debug_enabled():
        return
    print(f"[DEBUG] {message}", file=sys.stderr)


def registry_dir() -> Path:
    return Path.home() / ".ccb" / "run"


def registry_path_for_session(session_id: str) -> Path:
    return registry_dir() / f"{REGISTRY_PREFIX}{session_id}{REGISTRY_SUFFIX}"


def iter_registry_files() -> Iterable[Path]:
    current_dir = registry_dir()
    if not current_dir.exists():
        return []
    return sorted(current_dir.glob(f"{REGISTRY_PREFIX}*{REGISTRY_SUFFIX}"))


def coerce_updated_at(value: Any, fallback_path: Optional[Path] = None) -> int:
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


def normalize_path_for_match(value: str | Path | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        path = Path(raw).expanduser()
        try:
            raw = str(path.resolve())
        except Exception:
            raw = str(path.absolute())
    except Exception:
        pass
    normalized = raw.replace("\\", "/").rstrip("/")
    if os.name == "nt":
        normalized = normalized.lower()
    return normalized


def path_is_same_or_parent(parent: str | Path | None, child: str | Path | None) -> bool:
    normalized_parent = normalize_path_for_match(parent)
    normalized_child = normalize_path_for_match(child)
    if not normalized_parent or not normalized_child:
        return False
    if normalized_parent == normalized_child:
        return True
    if not normalized_child.startswith(normalized_parent):
        return False
    return normalized_child[len(normalized_parent) :].startswith("/")


def is_stale(updated_at: int, now: Optional[int] = None) -> bool:
    if updated_at <= 0:
        return True
    now_ts = int(time.time()) if now is None else int(now)
    return (now_ts - updated_at) > REGISTRY_TTL_SECONDS


def load_registry_file(path: Path) -> Optional[Dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            return data
    except Exception as exc:
        debug(f"Failed to read registry {path}: {exc}")
    return None


def provider_entry_from_legacy(data: Dict[str, Any], provider: str) -> Dict[str, Any]:
    """
    Read-compat shim for older flat registry records.
    New writes should prefer providers.<provider>.* only.
    """
    provider = (provider or "").strip().lower()
    out: Dict[str, Any] = {}

    if provider == "codex":
        for src_key, dst_key in [
            ("codex_pane_id", "pane_id"),
            ("pane_title_marker", "pane_title_marker"),
            ("codex_session_id", "codex_session_id"),
            ("codex_session_path", "codex_session_path"),
        ]:
            value = data.get(src_key)
            if value:
                out[dst_key] = value
    elif provider == "gemini":
        for src_key, dst_key in [
            ("gemini_pane_id", "pane_id"),
            ("pane_title_marker", "pane_title_marker"),
            ("gemini_session_id", "gemini_session_id"),
            ("gemini_session_path", "gemini_session_path"),
        ]:
            value = data.get(src_key)
            if value:
                out[dst_key] = value
    elif provider == "opencode":
        for src_key, dst_key in [
            ("opencode_pane_id", "pane_id"),
            ("pane_title_marker", "pane_title_marker"),
        ]:
            value = data.get(src_key)
            if value:
                out[dst_key] = value
    elif provider == "claude":
        value = data.get("claude_pane_id")
        if value:
            out["pane_id"] = value

    return out


def get_providers_map(data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    providers = data.get("providers")
    if isinstance(providers, dict):
        out: Dict[str, Dict[str, Any]] = {}
        for key, value in providers.items():
            if isinstance(key, str) and isinstance(value, dict):
                out[key.strip().lower()] = dict(value)
        return out

    out = {}
    for provider in ("codex", "gemini", "opencode", "claude"):
        entry = provider_entry_from_legacy(data, provider)
        if entry:
            out[provider] = entry
    return out


def provider_pane_alive(
    record: Dict[str, Any],
    provider: str,
    *,
    get_backend_for_session_fn=get_backend_for_session,
) -> bool:
    base_provider, _ = parse_qualified_provider(provider)
    providers = get_providers_map(record)
    entry = providers.get((provider or "").strip().lower())
    if not isinstance(entry, dict):
        entry = providers.get(base_provider)
    if not isinstance(entry, dict):
        return False

    pane_id = str(entry.get("pane_id") or "").strip()

    try:
        backend = get_backend_for_session_fn({"terminal": record.get("terminal", "tmux")})
    except Exception:
        backend = None
    if not backend:
        return False

    if not pane_id:
        return False

    try:
        return bool(backend.is_alive(pane_id))
    except Exception:
        return False
