from __future__ import annotations

import os


def random_token() -> str:
    return os.urandom(16).hex()


def normalize_connect_host(host: str) -> str:
    host = (host or "").strip()
    if not host or host in ("0.0.0.0",):
        return "127.0.0.1"
    if host in ("::", "[::]"):
        return "::1"
    return host


__all__ = ["normalize_connect_host", "random_token"]
