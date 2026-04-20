from __future__ import annotations

import socket
from pathlib import Path
from urllib.parse import urlparse

from .overlay import read_user_settings_payload


def claude_user_base_url(*, user_settings_path: Path) -> str:
    payload = read_user_settings_payload(user_settings_path)
    if payload is None:
        return ""
    env_payload = payload.get("env")
    if not isinstance(env_payload, dict):
        return ""
    return str(env_payload.get("ANTHROPIC_BASE_URL") or "").strip()


def should_drop_claude_base_url(value: str, *, local_tcp_listener_available_fn) -> bool:
    host, port = local_base_url_target(value)
    if host is None or port is None:
        return False
    return not local_tcp_listener_available_fn(host, port)


def local_base_url_target(value: str) -> tuple[str | None, int | None]:
    parsed = urlparse(str(value or "").strip())
    host = (parsed.hostname or "").strip().lower()
    if host not in {"127.0.0.1", "localhost", "::1"}:
        return None, None
    return host, parsed.port


def local_tcp_listener_available(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.2):
            return True
    except Exception:
        return False


__all__ = [
    "claude_user_base_url",
    "local_base_url_target",
    "local_tcp_listener_available",
    "should_drop_claude_base_url",
]
