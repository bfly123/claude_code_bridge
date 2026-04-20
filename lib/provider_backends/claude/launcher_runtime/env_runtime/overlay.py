from __future__ import annotations

import json
from pathlib import Path


def write_claude_settings_overlay(runtime_dir: Path, *, profile=None) -> Path | None:
    payload = read_agent_settings_payload(profile)
    if payload is None:
        return None
    sanitized = sanitized_settings_overlay(payload)
    if not sanitized:
        return None

    settings_path = runtime_dir / "claude-settings.json"
    settings_path.write_text(json.dumps(sanitized, ensure_ascii=False, indent=2), encoding="utf-8")
    return settings_path


def read_user_settings_payload(user_settings_path: Path) -> dict[str, object] | None:
    return read_settings_payload(user_settings_path)


def read_settings_payload(path: Path) -> dict[str, object] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def read_agent_settings_payload(profile) -> dict[str, object] | None:
    settings_path = agent_settings_path(profile)
    if settings_path is None:
        return None
    return read_settings_payload(settings_path)


def agent_settings_path(profile) -> Path | None:
    if profile is None:
        return None
    profile_root = getattr(profile, 'profile_root_path', None)
    if profile_root is None:
        return None
    settings_path = Path(profile_root) / "settings.json"
    if not settings_path.is_file():
        return None
    return settings_path


def sanitized_settings_overlay(payload: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in payload.items() if key != "env"}


__all__ = [
    "agent_settings_path",
    "read_agent_settings_payload",
    "read_settings_payload",
    "read_user_settings_payload",
    "sanitized_settings_overlay",
    "write_claude_settings_overlay",
]
