from __future__ import annotations

import json
from pathlib import Path


def write_claude_settings_overlay(runtime_dir: Path, *, user_settings_path: Path) -> Path | None:
    payload = read_user_settings_payload(user_settings_path)
    if payload is None:
        return None
    sanitized = sanitized_settings_overlay(payload)
    if not sanitized:
        return None

    settings_path = runtime_dir / "claude-settings.json"
    settings_path.write_text(json.dumps(sanitized, ensure_ascii=False, indent=2), encoding="utf-8")
    return settings_path


def read_user_settings_payload(user_settings_path: Path) -> dict[str, object] | None:
    try:
        payload = json.loads(user_settings_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def sanitized_settings_overlay(payload: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in payload.items() if key != "env"}


__all__ = ["read_user_settings_payload", "sanitized_settings_overlay", "write_claude_settings_overlay"]
